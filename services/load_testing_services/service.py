import logging
from datetime import datetime, timezone
from io import BytesIO

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from db.models import TestScript, Application, TestRun
from db.supabase_client import get_supabase, BUCKET_TEST_SCRIPTS, BUCKET_K6_RESULTS
from packages.k6_worker.producer import publish_load_test_job

logger = logging.getLogger(__name__)


async def get_scripts_for_application(
    db: AsyncSession,
    application_id: int
) -> list[TestScript]:
    result = await db.execute(
        select(TestScript).where(TestScript.application_id == application_id)
    )
    return result.scalars().all()


async def get_test_runs_for_script(
    db: AsyncSession,
    script_id: int
) -> list[TestRun]:
    result = await db.execute(
        select(TestRun)
        .where(TestRun.test_script_id == script_id)
        .order_by(TestRun.start_time.desc())
    )
    return result.scalars().all()


async def upload_script(
    db: AsyncSession,
    app_id: int,
    file,
    user_id: int
) -> TestScript:
    """Upload a .js k6 script to Supabase and register in DB"""
    from db.models import Application

    # Verify ownership
    app_result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.user_id == user_id
        )
    )
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Application not found or unauthorized.")

    # Upload to Supabase
    bucket_path = f"apps/{app_id}/scripts/{file.filename}"
    file_bytes = await file.read()

    try:
        get_supabase().storage.from_(BUCKET_TEST_SCRIPTS).upload(
            path=bucket_path,
            file=file_bytes,
            file_options={"content-type": "application/javascript"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Script upload failed: {str(e)}")

    # Register in DB
    script = TestScript(
        application_id=app_id,
        script_name=file.filename,
        storage_path=bucket_path
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return script


async def trigger_test_run(
    db: AsyncSession,
    script_id: int,
    user_id: int
) -> TestRun:
    # Verify script belongs to this user
    script_result = await db.execute(
        select(TestScript).join(Application)
        .where(
            TestScript.id == script_id,
            Application.user_id == user_id
        )
    )
    script = script_result.scalar_one_or_none()

    if not script:
        raise HTTPException(
            status_code=404,
            detail="Test script not found or unauthorized."
        )

    # Create TestRun with status "queued"
    test_run = TestRun(
        test_script_id=script_id,
        status="queued",
        start_time=datetime.now(timezone.utc),
        end_time=None,
        result_file_path=None
    )
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    # Publish to Kafka
    try:
        await publish_load_test_job(
            test_run_id=test_run.id,
            storage_path=script.storage_path,
            script_name=script.script_name,
            app_id=script.application_id,
            script_id=script.id
        )
        logger.info(f"Job {test_run.id} published to Kafka")
    except Exception as e:
        logger.error(f"Failed to publish job {test_run.id}: {e}")
        test_run.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to queue test: {str(e)}")

    return test_run


async def download_latest_result_for_script(
    db: AsyncSession,
    script_id: int,
    user_id: int
):
    script_result = await db.execute(
        select(TestScript).join(Application)
        .where(
            TestScript.id == script_id,
            Application.user_id == user_id
        )
    )
    script = script_result.scalar_one_or_none()

    if not script:
        raise HTTPException(
            status_code=404,
            detail="Test script not found or unauthorized."
        )

    run_result = await db.execute(
        select(TestRun)
        .where(
            TestRun.test_script_id == script_id,
            TestRun.status == "completed",
            TestRun.result_file_path.isnot(None)
        )
        .order_by(TestRun.end_time.desc().nullslast(), TestRun.start_time.desc())
    )
    test_run = run_result.scalars().first()

    if not test_run or not test_run.result_file_path:
        raise HTTPException(
            status_code=404,
            detail="No completed result file is available for this script."
        )

    try:
        data = get_supabase().storage.from_(BUCKET_K6_RESULTS).download(test_run.result_file_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to download result file: {exc}")

    file_name = test_run.result_file_path.split("/")[-1] or f"script-{script_id}-result.json"
    headers = {
        "Content-Disposition": f'attachment; filename="{file_name}"'
    }
    return StreamingResponse(
        BytesIO(data),
        media_type="application/json",
        headers=headers
    )