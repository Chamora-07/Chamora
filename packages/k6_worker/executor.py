import os
import asyncio
import shutil
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from .db import update_test_run

load_dotenv()

K6_SCRIPTS_BUCKET = "test_scripts"
K6_RESULTS_BUCKET = "k6_results"
SUPABASE_KEY_ = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ6d3ZtcnJyaHNqem1mZXlranNiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTkxMTAzNSwiZXhwIjoyMDkxNDg3MDM1fQ.Rpn86YcgsKN7P0pTw3yfPvhyaEa4ydaJjMo2eANIJAk"

def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = SUPABASE_KEY_
    if not url or not key:
        raise RuntimeError(
            f"SUPABASE_URL={'set' if url else 'MISSING'}, "
            f"SUPABASE_KEY_={'set' if key else 'MISSING'}"
        )
    return create_client(url, key)


async def execute_k6_run(
    test_run_id: int,
    storage_path: str,
    script_name: str,
    app_id: int,
    script_id: int
):
    run_dir     = f"/tmp/k6_{test_run_id}"
    scripts_dir = os.path.join(run_dir, "scripts")
    results_dir = os.path.join(run_dir, "results")
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    local_script = os.path.join(scripts_dir, script_name)
    local_result = os.path.join(results_dir, "result.json")

    try:
        # Step 1 — Mark as running
        await update_test_run(
            test_run_id,
            status="running",
            start_time=datetime.utcnow()
        )
        print(f"[Run {test_run_id}] Status → running")

        # Step 2 — Download script
        print(f"[Run {test_run_id}] Downloading from "
              f"bucket='{K6_SCRIPTS_BUCKET}' path='{storage_path}'")
        client = get_supabase()

        try:
            data = client.storage.from_(K6_SCRIPTS_BUCKET).download(storage_path)
        except Exception as e:
            raise RuntimeError(
                f"Download failed — bucket='{K6_SCRIPTS_BUCKET}' "
                f"path='{storage_path}' error={e}"
            )

        with open(local_script, "wb") as f:
            f.write(data)
        print(f"[Run {test_run_id}] Script saved ({len(data)} bytes)")

        # Step 3 — Run k6
        print(f"[Run {test_run_id}] Starting k6")
        process = await asyncio.create_subprocess_exec(
            "k6", "run",
            "--out", f"json={local_result}",
            local_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def stream_output():
            async for line in process.stdout:
                decoded = line.decode(errors="replace").rstrip()
                if decoded:
                    print(f"[Run {test_run_id}] k6: {decoded}")

        try:
            await asyncio.wait_for(
                asyncio.gather(stream_output(), process.wait()),
                timeout=3600
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("k6 timed out after 1 hour")

        if process.returncode != 0:
            stderr_out = await process.stderr.read()
            raise RuntimeError(
                f"k6 exited with code {process.returncode}:\n"
                f"{stderr_out.decode(errors='replace')}"
            )

        # Step 4 — Verify result
        if not os.path.exists(local_result):
            raise FileNotFoundError("k6 did not produce result.json")

        # Step 5 — Upload result
        remote_result_path = f"{app_id}/{script_id}/{test_run_id}_result.json"
        print(f"[Run {test_run_id}] Uploading result → {remote_result_path}")
        with open(local_result, "rb") as f:
            try:
                client.storage.from_(K6_RESULTS_BUCKET).upload(
                    path=remote_result_path,
                    file=f.read(),
                    file_options={"content-type": "application/json"}
                )
            except Exception as e:
                raise RuntimeError(f"Result upload failed: {e}")

        # Step 6 — Mark completed
        await update_test_run(
            test_run_id,
            status="completed",
            end_time=datetime.utcnow(),
            result_file_path=remote_result_path
        )
        print(f"[Run {test_run_id}] Status → completed")

    except Exception as e:
        print(f"[Run {test_run_id}] FAILED: {e}")
        try:
            await update_test_run(
                test_run_id,
                status="failed",
                end_time=datetime.utcnow()
            )
        except Exception as db_err:
            print(f"[Run {test_run_id}] DB update also failed: {db_err}")

    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
        print(f"[Run {test_run_id}] Cleaned up {run_dir}")