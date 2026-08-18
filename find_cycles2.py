import sys
sys.path.insert(0, "/app")
from app.core.supabase_client import get_supabase_client

sb = get_supabase_client()
runs = (sb.table("test_runs")
        .select("id,test_script_id,status,start_time,end_time,result_file_path")
        .order("id", desc=True).limit(50).execute().data)

completed = [r for r in runs if r.get("end_time")]
print(f"Total fetched: {len(runs)}   Completed: {len(completed)}\n")
print("=== COMPLETED (end_time set) ===")
for r in completed:
    print(f"  cycle_id={r['id']:>4}  status={r['status']:<10} script_id={r['test_script_id']}  start={r['start_time']}  end={r['end_time']}")
print("\n=== OPEN/running (end_time NULL) ===")
for r in runs:
    if not r.get("end_time"):
        print(f"  cycle_id={r['id']:>4}  status={r['status']:<10} script_id={r['test_script_id']}")
