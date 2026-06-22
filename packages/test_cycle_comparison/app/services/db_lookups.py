"""
Supabase REST lookups used by the cycle metrics fetcher.

The main backend writes these tables via SQLAlchemy; here we only read.
Kept synchronous to match the supabase-py client.
"""

from typing import Dict, List, Optional

from app.core.supabase_client import get_supabase_client


def get_cycle(cycle_id: int) -> Optional[dict]:
    """Fetch a test cycle (test_runs row) by id."""
    supabase = get_supabase_client()
    result = (
        supabase.table("test_runs")
        .select("id,test_script_id,status,start_time,end_time,result_file_path")
        .eq("id", cycle_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_script(script_id: int) -> Optional[dict]:
    """Fetch a test script by id."""
    supabase = get_supabase_client()
    result = (
        supabase.table("test_scripts")
        .select("id,application_id,script_name")
        .eq("id", script_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_application(application_id: int) -> Optional[dict]:
    """Fetch an application's monitoring metadata."""
    supabase = get_supabase_client()
    result = (
        supabase.table("applications")
        .select("id,name,victoria_metrics_url")
        .eq("id", application_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_endpoints(endpoint_ids: List[int]) -> List[dict]:
    """Fetch endpoints by id list. Preserves insertion order from DB."""
    if not endpoint_ids:
        return []
    supabase = get_supabase_client()
    result = (
        supabase.table("endpoints")
        .select("id,application_id,target_name,container_name")
        .in_("id", endpoint_ids)
        .execute()
    )
    return result.data or []


def get_cycle_context(cycle_id: int) -> Dict:
    """
    Assemble everything needed to fetch metrics for a cycle:
      cycle row + parent script + parent application (with VM URL).

    Raises ValueError if any link in the chain is missing or the cycle
    has no VM URL configured on its application.
    """
    cycle = get_cycle(cycle_id)
    if not cycle:
        raise ValueError(f"Test cycle {cycle_id} not found")

    script = get_script(cycle["test_script_id"])
    if not script:
        raise ValueError(
            f"Test script {cycle['test_script_id']} referenced by cycle "
            f"{cycle_id} not found"
        )

    application = get_application(script["application_id"])
    if not application:
        raise ValueError(
            f"Application {script['application_id']} referenced by script "
            f"{script['id']} not found"
        )

    if not application.get("victoria_metrics_url"):
        raise ValueError(
            f"Application {application['id']} has no victoria_metrics_url "
            f"configured"
        )

    return {
        "cycle": cycle,
        "script": script,
        "application": application,
    }
