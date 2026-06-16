#!/usr/bin/env python3
"""
SRE Telemetry Target Generator - AI Performance Intelligent Engine
Ingests the raw anomaly detection output (MLOutput2.csv), parses stringified metrics,
applies expert SRE diagnostic heuristics to generate high-fidelity target values,
and outputs a balanced training-ready instruction-tuning dataset (LLMAnalysisResults_Full.jsonl).
"""

import os
import csv
import json
import random
import pandas as pd
from datetime import datetime

# Set seed for reproducible data generation
random.seed(42)

def generate_synthetic_record(rc_type, idx):
    """
    Generates a highly realistic, mathematically consistent telemetry metric record
    and SRE expert reasoning template matching the diagnostic heuristics.
    """
    # Base defaults (nominal operation)
    cpu = random.uniform(0.10, 0.40)
    cpu_ratio = random.uniform(0.10, 0.40)
    mem_press = random.uniform(0.10, 0.50)
    mem_growth = random.uniform(-1e6, 1e6)
    latency = random.uniform(0.005, 0.02)
    error_rate = 0.0
    failures = 0
    restarts = False
    restart_flag = 0.0
    disk_io = random.uniform(0.01, 0.20)
    net_tp = random.uniform(50.0, 250.0)
    
    severity = random.choice(["WARNING", "CRITICAL"])
    ml_root_cause = "GENERAL_DEGRADATION"
    confidence = random.uniform(0.78, 0.92)
    
    if rc_type == "MEMORY_LEAK":
        mem_press = random.uniform(0.86, 0.98)
        mem_growth = random.uniform(15e6, 75e6)  # 15 to 75 MB/s growth
        cpu = random.uniform(0.25, 0.50)
        latency = random.uniform(0.06, 0.14)
        affected_component = "APPLICATION"
        evidence_summary = f"Detected high memory pressure ({mem_press:.2%}) and active growth rate of {mem_growth/1e6:.2f} MB/s."
        mem_gb = random.uniform(2.5, 8.5)
        reasoning = (
            f"The system shows a continuous memory increase reaching {mem_gb:.2f} GB "
            f"with critical memory pressure ({mem_press:.4f}). High growth trends coupled with degrading "
            f"latencies ({latency:.4f}s) strongly confirm an active memory leak inside the user application space."
        )
        
    elif rc_type == "CPU_SATURATION":
        cpu = random.uniform(0.86, 0.99)
        cpu_ratio = random.uniform(0.81, 0.98)
        latency = random.uniform(0.06, 0.16)
        affected_component = random.choice(["API_SERVER", "APPLICATION"])
        evidence_summary = f"Sustained CPU usage rate at {cpu:.2%} with node ratio {cpu_ratio:.2%}."
        reasoning = (
            f"Telemetry flags critical CPU utilization of {cpu:.4f}. The container-to-node allocation ratio "
            f"is saturated at {cpu_ratio:.4f}, resulting in queueing delays. Latency p95 rose to {latency:.4f}s, "
            f"confirming CPU core starvation is degrading thread execution times."
        )
        
    elif rc_type == "GC_PRESSURE":
        mem_press = random.uniform(0.72, 0.84)
        cpu = random.uniform(0.61, 0.84)
        latency = random.uniform(0.045, 0.095)
        affected_component = "JVM"
        evidence_summary = f"Coincident high memory pressure ({mem_press:.2%}) and elevated CPU usage ({cpu:.2%})."
        reasoning = (
            f"Both memory pressure ({mem_press:.4f}) and CPU utilization ({cpu:.4f}) are elevated simultaneously. "
            f"This pattern, accompanied by elevated transaction response times ({latency:.4f}s), indicates "
            f"the JVM or runtime is spending excessive cycles performing Garbage Collection sweeps, causing application freezes."
        )
        
    elif rc_type == "NETWORK_BOTTLENECK":
        net_tp = random.uniform(820.0, 1150.0)
        latency = random.uniform(0.08, 0.22)
        error_rate = random.uniform(0.02, 0.06)
        affected_component = "NETWORK"
        evidence_summary = f"High network throughput ({net_tp:.2f} Mbps) accompanied by degrading transaction times."
        reasoning = (
            f"The network adapter reports high sustained bandwidth utilization reaching {net_tp:.2f} Mbps. "
            f"High transmission speeds are causing queueing and packet retransmissions, leading to elevated "
            f"latencies ({latency:.4f}s) and high network-bound errors."
        )
        
    elif rc_type == "IO_BOTTLENECK":
        disk_io = random.uniform(0.81, 0.99)
        latency = random.uniform(0.06, 0.15)
        affected_component = "STORAGE"
        evidence_summary = f"Sustained disk write operations flagged at {disk_io:.2%} capacity."
        reasoning = (
            f"Storage adapter reports a massive write operations bottleneck with I/O rate at {disk_io:.4f}. "
            f"Transactions are stalled waiting on disk flush operations, resulting in write-blocked latency degradation."
        )
        
    elif rc_type == "RESOURCE_CONTENTION":
        latency = random.uniform(0.12, 0.38)
        cpu = random.uniform(0.05, 0.30)
        mem_press = random.uniform(0.10, 0.35)
        affected_component = "DATABASE"
        evidence_summary = f"General transaction degradation. Latency p95: {latency:.4f}s, CPU: {cpu:.2%}, Memory: {mem_press:.2%}."
        reasoning = (
            f"The system shows moderate degradation across multiple vectors (Latency={latency:.4f}s, "
            f"CPU={cpu:.4f}, Memory Pressure={mem_press:.4f}). This indicates general resource contention or "
            f"noisy-neighbor interference on the hosting database socket or network interface."
        )
        
    elif rc_type == "APPLICATION_BUG":
        error_rate = random.uniform(0.06, 0.22)
        failures = random.randint(5, 35)
        affected_component = "API_SERVER"
        evidence_summary = f"High transaction error rate of {error_rate:.2%} with a failure streak of {failures}."
        reasoning = (
            f"The application transaction log registers an elevated error rate of {error_rate:.4f} with a failure "
            f"streak of {failures}. Since system resources (CPU={cpu:.4f}, RAM press={mem_press:.4f}) are well within "
            f"nominal thresholds, this confirms a logic regression, database connection pool exhaustion, or internal bug."
        )
        
    elif rc_type == "CONFIGURATION_ISSUE":
        restarts = True
        restart_flag = random.choice([0.3333333333333333, 0.6666666666666666])
        failures = random.randint(0, 5)
        affected_component = "APPLICATION"
        evidence_summary = f"Container restart detected with failure streak of {failures} and restart flag at {restart_flag:.2%}."
        reasoning = (
            f"Container restarter logs flag active restarts (has_restart={restarts}, flag={restart_flag:.4f}). "
            f"The failure streak is recorded at {failures} consecutive transactions. This signature indicates "
            f"an unhealthy loop, pointing to a configuration mismatch, container probe crash, or deployment startup issue."
        )
    else:
        raise ValueError(f"Unknown root cause type: {rc_type}")
        
    mem_bytes = mem_press * 1e9
    mem_gb = mem_bytes / 1e9
    
    metrics_summary = json.dumps({
        "cpu_usage_rate": cpu,
        "memory_usage_gb": mem_gb,
        "memory_pressure": mem_press,
        "latency_p95": latency,
        "error_rate": error_rate,
        "failure_streak": failures,
        "has_restart": restarts,
        "restart_flag": restart_flag,
        "disk_io_rate": disk_io,
        "net_throughput": net_tp,
        "memory_growth_rate": mem_growth,
        "cpu_container_vs_node_ratio": cpu_ratio
    })
    
    return {
        "id": f"syn_{rc_type.lower()}_{idx:05d}",
        "application_id": random.choice([1, 2, 3]),
        "config_id": random.choice([1, 2, 3]),
        "window_timestamp": f"2026-05-27 {random.randint(0, 23):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}.000000+00",
        "ml_severity": severity,
        "ml_root_cause": ml_root_cause,
        "root_cause": rc_type,
        "confidence": round(confidence, 2),
        "affected_component": affected_component,
        "evidence": evidence_summary,
        "metrics_summary": metrics_summary,
        "analysis_reasoning": reasoning
    }

def generate_targets(csv_path, output_jsonl_path, target_per_class=150):
    print("=" * 70)
    print("AI Performance Engine - training data target Generator (Balanced)")
    print("=" * 70)
    
    print(f"Reading raw anomaly records from: {csv_path}")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Source file not found at {csv_path}")
        
    df = pd.read_csv(csv_path)
    print(f"✓ Successfully loaded {len(df)} telemetry records.")
    
    # SRE Categories list
    sre_categories = [
        'CONFIGURATION_ISSUE', 
        'MEMORY_LEAK', 
        'CPU_SATURATION', 
        'NETWORK_BOTTLENECK', 
        'APPLICATION_BUG', 
        'RESOURCE_CONTENTION', 
        'GC_PRESSURE', 
        'IO_BOTTLENECK'
    ]
    
    # Dictionary to collect records for each class
    dataset_records = {cat: [] for cat in sre_categories}
    
    # First, process existing records from MLOutput2.csv and assign them according to heuristics
    print("\n[1/3] Filtering and categorizing natural telemetry records...")
    for idx, row in df.iterrows():
        raw_evidence_str = row['evidence']
        try:
            metrics = json.loads(raw_evidence_str)
        except Exception:
            try:
                fixed_str = raw_evidence_str.replace('""', '"')
                metrics = json.loads(fixed_str)
            except Exception:
                continue
        
        cpu = metrics.get('cpu_usage_rate', 0.0)
        cpu_ratio = metrics.get('cpu_container_vs_node_ratio', 0.0)
        mem_bytes = metrics.get('memory_usage', 0.0)
        mem_gb = mem_bytes / 1e9
        mem_press = metrics.get('memory_pressure', 0.0)
        mem_growth = metrics.get('memory_growth_rate', 0.0)
        latency = metrics.get('latency_p95', 0.0)
        error_rate = metrics.get('error_rate', 0.0)
        failures = metrics.get('failure_streak', 0)
        restarts = metrics.get('has_restart', False)
        restart_flag = metrics.get('restart_flag', 0.0)
        disk_io = metrics.get('disk_io_rate', 0.0)
        net_tp = metrics.get('net_throughput', 0.0)
        
        # Expert Heuristics matching to categorize existing rows
        root_cause = None
        affected_component = "APPLICATION"
        confidence = 0.85
        evidence_summary = ""
        reasoning = ""
        
        if mem_press > 0.85 or (mem_growth > 5e6 and mem_press > 0.60):
            root_cause = "MEMORY_LEAK"
            affected_component = "APPLICATION"
            evidence_summary = f"Detected high memory pressure ({mem_press:.2%}) and active growth rate of {mem_growth/1e6:.2f} MB/s."
            reasoning = (
                f"The system shows a continuous memory increase reaching {mem_gb:.2f} GB "
                f"with critical memory pressure ({mem_press:.4f}). High growth trends coupled with degrading "
                f"latencies ({latency:.4f}s) strongly confirm an active memory leak inside the user application space."
            )
        elif cpu > 0.85 or (cpu_ratio > 0.80 and cpu > 0.60):
            root_cause = "CPU_SATURATION"
            affected_component = "API_SERVER" if latency > 0.05 else "APPLICATION"
            evidence_summary = f"Sustained CPU usage rate at {cpu:.2%} with node ratio {cpu_ratio:.2%}."
            reasoning = (
                f"Telemetry flags critical CPU utilization of {cpu:.4f}. The container-to-node allocation ratio "
                f"is saturated at {cpu_ratio:.4f}, resulting in queueing delays. Latency p95 rose to {latency:.4f}s, "
                f"confirming CPU core starvation is degrading thread execution times."
            )
        elif mem_press > 0.70 and cpu > 0.60 and latency > 0.04:
            root_cause = "GC_PRESSURE"
            affected_component = "JVM"
            evidence_summary = f"Coincident high memory pressure ({mem_press:.2%}) and elevated CPU usage ({cpu:.2%})."
            reasoning = (
                f"Both memory pressure ({mem_press:.4f}) and CPU utilization ({cpu:.4f}) are elevated simultaneously. "
                f"This pattern, accompanied by elevated transaction response times ({latency:.4f}s), indicates "
                f"the JVM or runtime is spending excessive cycles performing Garbage Collection sweeps, causing application freezes."
            )
        elif restarts or restart_flag > 0.20 or failures > 10:
            root_cause = "CONFIGURATION_ISSUE"
            affected_component = "APPLICATION"
            evidence_summary = f"Container restart detected with failure streak of {failures} and restart flag at {restart_flag:.2%}."
            reasoning = (
                f"Container restarter logs flag active restarts (has_restart={restarts}, flag={restart_flag:.4f}). "
                f"The failure streak is recorded at {failures} consecutive transactions. This signature indicates "
                f"an unhealthy loop, pointing to a configuration mismatch, container probe crash, or deployment startup issue."
            )
        elif net_tp > 800.0 or (latency > 0.08 and net_tp > 500.0 and error_rate > 0.02):
            root_cause = "NETWORK_BOTTLENECK"
            affected_component = "NETWORK"
            evidence_summary = f"High network throughput ({net_tp:.2f} Mbps) accompanied by degrading transaction times."
            reasoning = (
                f"The network adapter reports high sustained bandwidth utilization reaching {net_tp:.2f} Mbps. "
                f"High transmission speeds are causing queueing and packet retransmissions, leading to elevated "
                f"latencies ({latency:.4f}s) and high network-bound errors."
            )
        elif disk_io > 0.80:
            root_cause = "IO_BOTTLENECK"
            affected_component = "STORAGE"
            evidence_summary = f"Sustained disk write operations flagged at {disk_io:.2%} capacity."
            reasoning = (
                f"Storage adapter reports a massive write operations bottleneck with I/O rate at {disk_io:.4f}. "
                f"Transactions are stalled waiting on disk flush operations, resulting in write-blocked latency degradation."
            )
        elif error_rate > 0.05 or failures > 0:
            root_cause = "APPLICATION_BUG"
            affected_component = "API_SERVER"
            evidence_summary = f"High transaction error rate of {error_rate:.2%} with a failure streak of {failures}."
            reasoning = (
                f"The application transaction log registers an elevated error rate of {error_rate:.4f} with a failure "
                f"streak of {failures}. Since system resources (CPU={cpu:.4f}, RAM press={mem_press:.4f}) are well within "
                f"nominal thresholds, this confirms a logic regression, database connection pool exhaustion, or internal bug."
            )
        else:
            root_cause = "RESOURCE_CONTENTION"
            affected_component = "DATABASE"
            evidence_summary = f"General transaction degradation. Latency p95: {latency:.4f}s, CPU: {cpu:.2%}, Memory: {mem_press:.2%}."
            reasoning = (
                f"The system shows moderate degradation across multiple vectors (Latency={latency:.4f}s, "
                f"CPU={cpu:.4f}, Memory Pressure={mem_press:.4f}). This indicates general resource contention or "
                f"noisy-neighbor interference on the hosting database socket or network interface."
            )
            
        if root_cause in dataset_records:
            # Reconstruct metric summary
            metrics_summary = json.dumps({
                "cpu_usage_rate": cpu,
                "memory_usage_gb": mem_gb,
                "memory_pressure": mem_press,
                "latency_p95": latency,
                "error_rate": error_rate,
                "failure_streak": failures,
                "has_restart": restarts,
                "restart_flag": restart_flag,
                "disk_io_rate": disk_io,
                "net_throughput": net_tp,
                "memory_growth_rate": mem_growth,
                "cpu_container_vs_node_ratio": cpu_ratio
            })
            
            rec = {
                "id": row.get('id', f"rec_{idx:05d}"),
                "application_id": int(row.get('application_id', 1)),
                "config_id": int(row.get('config_id', 1)),
                "window_timestamp": row.get('window_timestamp', str(datetime.utcnow())),
                "ml_severity": row.get('severity', 'WARNING'),
                "ml_root_cause": row.get('root_cause', 'GENERAL_DEGRADATION'),
                "root_cause": root_cause,
                "confidence": confidence,
                "affected_component": affected_component,
                "evidence": evidence_summary,
                "metrics_summary": metrics_summary,
                "analysis_reasoning": reasoning
            }
            dataset_records[root_cause].append(rec)

    # Print natural counts
    print("\nNatural record counts after heuristics matching:")
    for cat in sre_categories:
        print(f" - {cat}: {len(dataset_records[cat])} records")

    # Second, sample natural records up to target_per_class, and synthesize deficit
    print(f"\n[2/3] Balancing categories to exactly {target_per_class} records each...")
    balanced_records = []
    
    for cat in sre_categories:
        naturals = dataset_records[cat]
        if len(naturals) >= target_per_class:
            # Down-sample natural records randomly to target_per_class
            random.shuffle(naturals)
            selected = naturals[:target_per_class]
            balanced_records.extend(selected)
            print(f" ✓ {cat}: Selected {len(selected)} natural records (down-sampled from {len(naturals)})")
        else:
            # Keep all natural records and generate synthetic ones for the deficit
            balanced_records.extend(naturals)
            deficit = target_per_class - len(naturals)
            print(f" + {cat}: Kept {len(naturals)} natural records. Generating {deficit} synthetic records...")
            for i in range(deficit):
                syn_rec = generate_synthetic_record(cat, len(naturals) + i)
                balanced_records.append(syn_rec)
                
    # Shuffle the final balanced dataset to mix classes
    random.shuffle(balanced_records)
    
    # Write to final JSONL file
    print(f"\n[3/3] Writing balanced dataset to {output_jsonl_path}...")
    with open(output_jsonl_path, 'w') as f_out:
        for rec in balanced_records:
            f_out.write(json.dumps(rec) + "\n")
            
    print("\n" + "=" * 70)
    print("🎉 SUCCESS: BALANCED GOLDEN SRE TRAINING DATASET GENERATED!")
    print(f"File saved to: {os.path.abspath(output_jsonl_path)}")
    print(f"Total processed records: {len(balanced_records)}")
    print(f"Distribution per class: exactly {target_per_class} records for all 8 SRE classes!")
    print("=" * 70)

if __name__ == "__main__":
    csv_path = "MLOutput2.csv"
    output_jsonl = "LLMAnalysisResults_Full.jsonl"
    try:
        generate_targets(csv_path, output_jsonl, target_per_class=150)
    except Exception as e:
        print(f"\n✗ Data generation failed: {e}")
