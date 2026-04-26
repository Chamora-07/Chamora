from app.core.supabase_client import get_supabase_client


def handle_test_comparison(question: str, app_id: str):
    supabase = get_supabase_client()

    # For now: get latest 2 test runs
    result = (
        supabase.table("test_runs")
        .select("*")
        .eq("app_id", app_id)
        .order("created_at", desc=True)
        .limit(2)
        .execute()
    )

    data = result.data

    if len(data) < 2:
        return {
            "answer": "Not enough test runs to compare.",
            "mode": "advisory"
        }

    run1, run2 = data[0], data[1]

    summary = f"""
Test Comparison Summary:

Run 1:
- ID: {run1['id']}
- Status: {run1.get('status')}
- Duration: {run1.get('duration')}

Run 2:
- ID: {run2['id']}
- Status: {run2.get('status')}
- Duration: {run2.get('duration')}
"""

    return {
        "answer": summary,
        "mode": "advisory"
    }