#!/usr/bin/env python3
"""
Validation & CSV Export Pipeline for Custom Fine-Tuned qwen-sre Model
"""
import sys
import argparse
import pandas as pd
import json
from tqdm import tqdm

from ai_performance_llm_engine import AIPerformanceAnalysisEngine

def parse_args():
    parser = argparse.ArgumentParser(description="Run SRE Diagnostics using Custom Fine-Tuned Model and Export to CSV")
    parser.add_argument(
        "--limit", 
        type=int, 
        default=10, 
        help="Number of records to process from MLOutput2.csv (default: 10)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="LLMAnalysisResults_FineTuned.csv", 
        help="Output CSV file path (default: LLMAnalysisResults_FineTuned.csv)"
    )
    parser.add_argument(
        "--model", 
        type=str, 
        default="qwen-sre", 
        help="Model name registered in Ollama (default: qwen-sre)"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    print("=" * 80)
    print(f"SRE DIAGNOSTIC PIPELINE - MODEL: '{args.model}'")
    print("=" * 80)

    # 1. Initialize Engine
    print(f"\n[1/4] Initializing SRE engine with model '{args.model}'...")
    try:
        engine = AIPerformanceAnalysisEngine(model_name=args.model)
    except Exception as e:
        print(f"❌ Error initializing engine: {e}")
        sys.exit(1)

    # 2. Load Telemetry Metrics
    print("\n[2/4] Loading telemetry metric records from MLOutput2.csv...")
    try:
        df = pd.read_csv("MLOutput2.csv")
        total_available = len(df)
        print(f"✓ Loaded {total_available} anomaly records successfully.")
    except Exception as e:
        print(f"❌ Error loading MLOutput2.csv: {e}")
        sys.exit(1)

    # Limit records to process
    limit = min(args.limit, total_available)
    records_to_process = df.head(limit)
    print(f"👉 Scheduled to process the first {limit} records.")

    # 3. Process records with progress bar
    print(f"\n[3/4] Running active diagnostic inference on {limit} records...")
    results_list = []
    
    for idx, row in tqdm(records_to_process.iterrows(), total=limit, desc="Analyzing"):
        record = row.to_dict()
        
        try:
            # Process metric anomalies using custom fine-tuned model
            result = engine.process_ml_output(record)
            
            # Append result
            results_list.append({
                'id': result.id,
                'ml_severity': result.ml_severity,
                'ml_root_cause': result.ml_root_cause,
                'root_cause': result.root_cause,
                'confidence': float(result.confidence),
                'affected_component': result.affected_component,
                'evidence': result.evidence,
                'analysis_reasoning': result.analysis_reasoning,
                'metrics_summary': result.metrics_summary,
                'created_at': result.created_at
            })
        except Exception as e:
            print(f"\n⚠ Warning: Failed to process record {idx}: {e}")

    # 4. Save results to CSV
    print(f"\n[4/4] Saving diagnostic results to CSV...")
    if not results_list:
        print("❌ No results generated. Skip writing file.")
        sys.exit(1)
        
    try:
        results_df = pd.DataFrame(results_list)
        results_df.to_csv(args.output, index=False)
        print(f"\n" + "=" * 80)
        print(f"🎉 SUCCESS: Diagnostic results exported successfully!")
        print(f"📁 CSV File: {args.output}")
        print(f"📊 Processed Records: {len(results_list)}")
        print("=" * 80)
        
        # Display short summary of predictions
        print("\nPredicted Root Causes Distribution:")
        print(results_df['root_cause'].value_counts().to_string())
        
        print("\nAffected Components Distribution:")
        print(results_df['affected_component'].value_counts().to_string())
        
        print(f"\nAverage Diagnosis Confidence: {results_df['confidence'].mean():.2%}")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error exporting CSV file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
