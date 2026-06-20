#!/usr/bin/env python3
"""
Example usage of AI Performance Analysis Engine
Demonstrates both synthetic and LLM-based analysis
"""

import sys
import json
import pandas as pd
from datetime import datetime

# Add the module to path
sys.path.insert(0, '/mnt/user-data/outputs')

from ai_performance_llm_engine import (
    AIPerformanceAnalysisEngine,
    MetricsAnalyzer,
    QwenLLMAnalyzer
)


def example_1_basic_usage():
    """Example 1: Basic usage with Qwen LLM"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Usage - Qwen LLM Analysis")
    print("="*70)
    
    # Initialize engine (LLM is mandatory)
    engine = AIPerformanceAnalysisEngine()
    
    # Resolve input path
    import os
    input_path = '/mnt/user-data/uploads/MLOutput.csv'
    if not os.path.exists(input_path):
        input_path = 'MLOutput.csv'
    if not os.path.exists(input_path):
        print("⚠ MLOutput.csv not found. Skip Example 1.")
        return None
        
    # Process the ML output file
    print("\nProcessing ML output CSV file...")
    processed = engine.process_file(
        input_csv_path=input_path,
        output_csv_path='LLMAnalysisResults_Output.csv',
        limit=10  # Process first 10 records for demo
    )
    
    # Print summary
    print("\n" + "-"*70)
    print("ANALYSIS SUMMARY")
    print("-"*70)
    stats = engine.get_summary_stats()
    print(json.dumps(stats, indent=2))
    
    return engine


def example_2_with_llm():
    """Example 2: Using Qwen LLM and checking availability"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Qwen LLM Check & Run")
    print("="*70)
    
    import os
    print("\nChecking LLM availability...")
    llm = QwenLLMAnalyzer(model_name="qwen:4b")
    
    if not llm.available:
        print("⚠ LLM not available. Install and start Ollama:")
        print("  1. Install: https://ollama.ai")
        print("  2. Run: ollama run qwen:4b")
        print("  3. Then re-run this script")
        return None
    
    print("✓ LLM is available!")
    
    # Initialize engine
    engine = AIPerformanceAnalysisEngine()
    
    # Resolve input path
    input_path = '/mnt/user-data/uploads/MLOutput.csv'
    if not os.path.exists(input_path):
        input_path = 'MLOutput.csv'
    if not os.path.exists(input_path):
        print("⚠ MLOutput.csv not found. Skip Example 2.")
        return None
        
    # Process file
    print("\nProcessing ML output with LLM analysis...")
    processed = engine.process_file(
        input_csv_path=input_path,
        output_csv_path='LLMAnalysisResults_LLM.csv',
        limit=5  # Use smaller limit for LLM (slower)
    )
    
    # Print summary
    print("\n" + "-"*70)
    print("ANALYSIS SUMMARY")
    print("-"*70)
    stats = engine.get_summary_stats()
    print(json.dumps(stats, indent=2))
    
    return engine


def example_3_detailed_analysis():
    """Example 3: Detailed analysis of specific records"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Detailed Analysis - Single Record Deep Dive")
    print("="*70)
    
    import os
    engine = AIPerformanceAnalysisEngine()
    
    # Resolve input path
    input_path = '/mnt/user-data/uploads/MLOutput.csv'
    if not os.path.exists(input_path):
        input_path = 'MLOutput.csv'
    if not os.path.exists(input_path):
        print("⚠ MLOutput.csv not found. Skip Example 3.")
        return
        
    # Read one record
    df = pd.read_csv(input_path)
    record = df.iloc[0].to_dict()
    
    print(f"\nAnalyzing record: {record['id']}")
    print(f"Application ID: {record['application_id']}")
    print(f"Config ID: {record['config_id']}")
    print(f"Timestamp: {record['window_timestamp']}")
    print(f"ML Severity: {record['severity']}")
    print(f"ML Root Cause: {record['root_cause']}")
    
    # Perform analysis
    result = engine.process_ml_output(record)
    
    print("\n" + "-"*70)
    print("LLM ANALYSIS RESULTS")
    print("-"*70)
    print(f"Root Cause:        {result.root_cause}")
    print(f"Confidence:        {result.confidence:.2%}")
    print(f"Affected Component: {result.affected_component}")
    print(f"Evidence:          {result.evidence}")
    print(f"Analysis Reasoning: {result.analysis_reasoning}")
    
    print("\n" + "-"*70)
    print("METRICS SUMMARY")
    print("-"*70)
    for metric, value in result.metrics_summary.items():
        print(f"{metric:.<40} {value}")


def example_4_threshold_analysis():
    """Example 4: Analyze threshold violations"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Threshold Analysis & Anomaly Detection")
    print("="*70)
    
    analyzer = MetricsAnalyzer()
    
    # Resolve input path
    import os
    input_path = '/mnt/user-data/uploads/MLOutput.csv'
    if not os.path.exists(input_path):
        input_path = 'MLOutput.csv'
    if not os.path.exists(input_path):
        print("⚠ MLOutput.csv not found. Skip Example 4.")
        return
        
    # Read and analyze first 5 records
    df = pd.read_csv(input_path)
    
    for idx in range(min(5, len(df))):
        record = df.iloc[idx]
        metrics = analyzer.parse_metrics(record['evidence'])
        
        if metrics:
            anomalies, severity_scores = analyzer.identify_anomalies(metrics)
            correlations = analyzer.correlate_metrics(metrics, anomalies)
            
            print(f"\n--- Record {idx + 1} ---")
            print(f"Anomalies detected: {len(anomalies)}")
            if anomalies:
                for anomaly in anomalies:
                    score = severity_scores.get(anomaly, 0)
                    print(f"  • {anomaly}: severity {score:.2f}x threshold")
            
            print(f"Correlations:")
            for key, val in correlations.items():
                print(f"  • {key}: {'YES' if val else 'NO'}")


def example_5_batch_processing():
    """Example 5: Full batch processing with statistics"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Full Batch Processing (All Records)")
    print("="*70)
    
    import os
    engine = AIPerformanceAnalysisEngine()
    
    # Resolve input path
    input_path = '/mnt/user-data/uploads/MLOutput.csv'
    if not os.path.exists(input_path):
        input_path = 'MLOutput.csv'
    if not os.path.exists(input_path):
        print("⚠ MLOutput.csv not found. Skip Example 5.")
        return
        
    print("\nProcessing all records in ML output file...")
    processed = engine.process_file(
        input_csv_path=input_path,
        output_csv_path='LLMAnalysisResults_Full.csv',
        limit=None  # Process all
    )
    
    # Detailed statistics
    print("\n" + "-"*70)
    print("DETAILED STATISTICS")
    print("-"*70)
    
    stats = engine.get_summary_stats()
    print(f"Total Records Processed: {stats.get('total_records', 0)}")
    
    print("\nRoot Cause Distribution:")
    for cause, count in sorted(
        stats.get('root_cause_distribution', {}).items(),
        key=lambda x: x[1],
        reverse=True
    ):
        percentage = (count / stats['total_records']) * 100
        print(f"  {cause:.<30} {count:>3} ({percentage:>5.1f}%)")
    
    print("\nAffected Component Distribution:")
    for component, count in sorted(
        stats.get('affected_component_distribution', {}).items(),
        key=lambda x: x[1],
        reverse=True
    ):
        percentage = (count / stats['total_records']) * 100
        print(f"  {component:.<30} {count:>3} ({percentage:>5.1f}%)")
    
    print("\nConfidence Metrics:")
    print(f"  Average Confidence: {stats.get('avg_confidence', 0):.2%}")
    print(f"  Min Confidence:     {stats.get('min_confidence', 0):.2%}")
    print(f"  Max Confidence:     {stats.get('max_confidence', 0):.2%}")


def example_6_database_schema():
    """Example 6: Show database schema for storing results"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Database Schema for Storing LLM Analysis")
    print("="*70)
    
    schema = """
PostgreSQL Schema (example):

CREATE TABLE llm_analysis_results (
    -- Identifiers & Timestamps
    id UUID PRIMARY KEY,
    application_id INTEGER NOT NULL,
    config_id INTEGER NOT NULL,
    window_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- ML Model Output (for reference)
    ml_severity VARCHAR(50) NOT NULL,
    ml_root_cause VARCHAR(100) NOT NULL,
    
    -- LLM Analysis Results
    root_cause VARCHAR(100) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    affected_component VARCHAR(100) NOT NULL,
    evidence TEXT NOT NULL,
    
    -- Analysis Details
    analysis_reasoning TEXT,
    metrics_summary JSONB,
    
    -- Indexing
    CREATE INDEX idx_app_id_timestamp ON llm_analysis_results(application_id, window_timestamp);
    CREATE INDEX idx_root_cause ON llm_analysis_results(root_cause);
    CREATE INDEX idx_affected_component ON llm_analysis_results(affected_component);
    CREATE INDEX idx_confidence ON llm_analysis_results(confidence);
);

-- Aggregation queries:

-- 1. Most common root causes by application
SELECT 
    application_id,
    root_cause,
    COUNT(*) as frequency,
    AVG(confidence) as avg_confidence
FROM llm_analysis_results
WHERE window_timestamp > NOW() - INTERVAL '24 hours'
GROUP BY application_id, root_cause
ORDER BY frequency DESC;

-- 2. Components with most issues
SELECT 
    affected_component,
    COUNT(*) as issue_count,
    AVG(confidence) as avg_confidence
FROM llm_analysis_results
WHERE window_timestamp > NOW() - INTERVAL '7 days'
GROUP BY affected_component
ORDER BY issue_count DESC;

-- 3. High-confidence anomalies
SELECT 
    id, application_id, window_timestamp,
    root_cause, confidence, affected_component, evidence
FROM llm_analysis_results
WHERE confidence > 0.8
  AND window_timestamp > NOW() - INTERVAL '24 hours'
ORDER BY confidence DESC, window_timestamp DESC;
"""
    
    print(schema)
    
    # Also show JSONL format example
    print("\n" + "-"*70)
    print("JSONL Format (for document databases):")
    print("-"*70)
    
    example_record = {
        "id": "00112ba4-3c37-4dde-b7dd-65e134b899e2",
        "application_id": 1,
        "config_id": 1,
        "window_timestamp": "2026-04-23T18:24:08.890170+00:00",
        "ml_severity": "WARNING",
        "ml_root_cause": "GENERAL_DEGRADATION",
        "root_cause": "MEMORY_LEAK",
        "confidence": 0.85,
        "affected_component": "APPLICATION",
        "evidence": "Detected memory growth rate of -991.27 MB/s with memory usage at 49.12GB",
        "analysis_reasoning": "Memory pressure and growth indicate active memory leak",
        "metrics_summary": {
            "cpu_usage_rate": 0.0066,
            "memory_usage_gb": 49.12,
            "memory_pressure": 0.127,
            "latency_p95": 0.0118,
            "error_rate": 0.0
        },
        "created_at": "2026-05-12T10:30:45.123456"
    }
    
    print(json.dumps(example_record, indent=2))


def example_7_pipeline_integration():
    """Example 7: Show how to integrate into a full pipeline"""
    print("\n" + "="*70)
    print("EXAMPLE 7: Full Pipeline Integration")
    print("="*70)
    
    integration_code = """
# Full AI Performance Intelligence Engine Pipeline

import kafka  # For consuming metrics
import database  # Your database module

# Step 1: Consume metrics (from monitoring)
metrics_consumer = kafka.KafkaConsumer('system-metrics')

# Step 2: Rule-based engine (your component)
rule_engine = RuleBasedPerformanceEngine()

# Step 3: ML Model (your component)
ml_model = MLPerformanceModel()

# Step 4: LLM Analysis (our component - this module)
llm_engine = AIPerformanceAnalysisEngine()

# Step 5: Store results
db = database.PostgresConnection()

# Main loop
for metric_batch in metrics_consumer:
    # Apply rule-based engine
    rule_output = rule_engine.evaluate(metric_batch)
    
    # Apply ML model
    ml_output = ml_model.predict(rule_output)
    
    # Apply LLM analysis
    llm_analysis = llm_engine.process_ml_output(ml_output)
    
    # Store in database
    db.insert('llm_analysis_results', {
        'id': llm_analysis.id,
        'application_id': llm_analysis.application_id,
        'config_id': llm_analysis.config_id,
        'window_timestamp': llm_analysis.window_timestamp,
        'ml_severity': llm_analysis.ml_severity,
        'ml_root_cause': llm_analysis.ml_root_cause,
        'root_cause': llm_analysis.root_cause,
        'confidence': llm_analysis.confidence,
        'affected_component': llm_analysis.affected_component,
        'evidence': llm_analysis.evidence,
        'analysis_reasoning': llm_analysis.analysis_reasoning,
        'metrics_summary': llm_analysis.metrics_summary,
        'created_at': llm_analysis.created_at,
    })
    
    # Optional: Trigger alerts for high-confidence issues
    if llm_analysis.confidence > 0.8:
        alert_service.notify({
            'severity': 'HIGH',
            'root_cause': llm_analysis.root_cause,
            'component': llm_analysis.affected_component,
            'evidence': llm_analysis.evidence,
            'timestamp': llm_analysis.window_timestamp,
        })

# Use the analysis for:
# - Real-time alerting
# - Historical trend analysis
# - Automated remediation
# - SLA tracking
# - Performance optimization recommendations
"""
    
    print(integration_code)


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("AI PERFORMANCE INTELLIGENT ENGINE - EXAMPLES")
    print("LLM-Based Root Cause Analysis")
    print("="*70)
    
    try:
        # Run examples
        example_1_basic_usage()
        example_3_detailed_analysis()
        example_4_threshold_analysis()
        example_5_batch_processing()
        example_6_database_schema()
        example_7_pipeline_integration()
        
        # Try LLM example (will gracefully degrade if not available)
        try:
            example_2_with_llm()
        except Exception as e:
            print(f"\nNote: LLM example skipped ({e})")
        
        print("\n" + "="*70)
        print("✓ ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("="*70)
        print("\nOutput files created:")
        print("  - LLMAnalysisResults_Synthetic.csv (50 records)")
        print("  - LLMAnalysisResults_Full.csv (all records)")
        print("  - Corresponding .jsonl files for database ingestion")
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
