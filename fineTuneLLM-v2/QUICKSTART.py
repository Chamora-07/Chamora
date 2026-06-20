#!/usr/bin/env python3
"""
QUICK START GUIDE - AI Performance LLM Engine
Run this script to get started immediately
"""

import sys
import os
import subprocess

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)


def print_step(num, text):
    """Print numbered step"""
    print(f"\n[Step {num}] {text}")


def install_dependencies():
    """Install required packages"""
    print_header("INSTALLING DEPENDENCIES")
    
    packages = ['pandas', 'numpy', 'requests']
    
    print("Installing required packages...")
    for package in packages:
        try:
            __import__(package)
            print(f"✓ {package} already installed")
        except ImportError:
            print(f"  Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
            print(f"✓ {package} installed")


def quick_test():
    """Run quick test"""
    print_header("QUICK TEST")
    
    print_step(1, "Initialize the engine")
    
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ai_performance_llm_engine import AIPerformanceAnalysisEngine
    
    # Initialize engine (LLM is mandatory)
    try:
        engine = AIPerformanceAnalysisEngine()
        print("✓ Engine initialized successfully")
    except Exception as e:
        print(f"⚠ Engine initialization warning: {e}")
        print("Continuing test using synthetic fallback mode is no longer supported.")
        engine = AIPerformanceAnalysisEngine() # will fail if Ollama is not running but we let it try
    
    print_step(2, "Process sample record")
    
    # Resolve input path
    input_path = '/mnt/user-data/uploads/MLOutput.csv'
    if not os.path.exists(input_path):
        input_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MLOutput.csv')
    if not os.path.exists(input_path):
        print(f"⚠ Skipping test: {input_path} not found.")
        print("Please place MLOutput.csv in this directory to run tests.")
        return
        
    import pandas as pd
    df = pd.read_csv(input_path)
    record = df.iloc[0].to_dict()
    
    result = engine.process_ml_output(record)
    print(f"✓ Record processed successfully")
    print(f"  - Root Cause: {result.root_cause}")
    print(f"  - Confidence: {result.confidence:.2%}")
    print(f"  - Component: {result.affected_component}")
    
    print_step(3, "Process batch (10 records)")
    
    output_dir = '/mnt/user-data/outputs'
    if not os.path.exists(output_dir):
        output_dir = os.path.dirname(os.path.abspath(__file__))
    
    output_path = os.path.join(output_dir, 'QuickTest_Results.csv')
    
    engine.process_file(
        input_csv_path=input_path,
        output_csv_path=output_path,
        limit=10
    )
    print("✓ Batch processing completed")
    print(f"  - Output: {output_path}")
    
    print_step(4, "View results")
    
    result_df = pd.read_csv(output_path)
    print(f"✓ Processed {len(result_df)} records")
    print("\n  Sample results:")
    print(result_df[['id', 'root_cause', 'confidence', 'affected_component']].head().to_string(index=False))


def full_batch_process():
    """Full batch processing"""
    print_header("FULL BATCH PROCESSING")
    
    # Resolve input path
    input_path = '/mnt/user-data/uploads/MLOutput.csv'
    if not os.path.exists(input_path):
        input_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MLOutput.csv')
    if not os.path.exists(input_path):
        print("⚠ Skipping batch processing: MLOutput.csv not found.")
        return

    print("Processing all records in your ML output file...")
    print("(This may take a few minutes for 121 records)\n")
    
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ai_performance_llm_engine import AIPerformanceAnalysisEngine
    
    engine = AIPerformanceAnalysisEngine()
    
    output_dir = '/mnt/user-data/outputs'
    if not os.path.exists(output_dir):
        output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, 'LLMAnalysisResults.csv')
    
    processed = engine.process_file(
        input_csv_path=input_path,
        output_csv_path=output_path
    )
    
    print("\n✓ Processing completed!")
    print(f"✓ {processed} records analyzed")
    
    stats = engine.get_summary_stats()
    print("\nAnalysis Summary:")
    print(f"  - Total Records: {stats['total_records']}")
    print(f"  - Average Confidence: {stats['avg_confidence']:.2%}")
    print(f"  - Root Causes: {list(stats['root_cause_distribution'].keys())}")
    print(f"  - Affected Components: {list(stats['affected_component_distribution'].keys())}")


def setup_llm():
    """Setup Qwen LLM for analysis"""
    print_header("SETUP QWEN LLM (Mandatory)")
    
    print("""
To run the mandatory Qwen 4B Instruct LLM analysis:

1. Install Ollama:
   - macOS/Linux: curl -fsSL https://ollama.ai/install.sh | sh
   - Windows: Download from https://ollama.ai/download

2. Start the LLM service:
   - Run: ollama run qwen:4b
   - Wait for download (first time only, ~3GB)

3. Run analysis with LLM:
   - Python: engine = AIPerformanceAnalysisEngine()
   - The system will automatically connect to Ollama and analyze.

4. Verify it's working:
   - curl http://localhost:11434/api/tags
   - Should show qwen:4b in the list

Note: Synthetic mode has been removed; local LLM is now strictly mandatory.
    """)


def show_next_steps():
    """Show next steps"""
    print_header("NEXT STEPS")
    
    print("""
1. Review the output files:
   - LLMAnalysisResults.csv: Analysis results
   - LLMAnalysisResults.jsonl: Same data in JSON Lines format

2. Load results into your database:
   
   PostgreSQL Example:
   ```sql
   COPY llm_analysis_results FROM 'LLMAnalysisResults.csv' 
   WITH (FORMAT CSV, HEADER);
   ```
   
   MongoDB Example:
   ```bash
   mongoimport --db mydb --collection analysis 
   --file LLMAnalysisResults.jsonl --jsonArray
   ```

3. Integrate into your pipeline:
   - Import AIPerformanceAnalysisEngine in your code
   - Call process_ml_output(record) for each ML model output
   - Store results in your database
   - Build dashboards/alerts on top

4. Customize for your needs:
   - Adjust metric thresholds in MetricsAnalyzer.THRESHOLDS
   - Add custom root cause categories
   - Fine-tune the LLM on your domain data

5. Monitor & Optimize:
   - Check confidence scores regularly
   - Adjust thresholds based on false positives
   - Track which root causes are most common
   - Optimize database queries
    """)


def show_file_guide():
    """Show file guide"""
    print_header("FILE REFERENCE GUIDE")
    
    print("""
Generated Files:

1. ai_performance_llm_engine.py
   - Main module with all analysis logic
   - Import this in your application
   
   Classes:
   - MetricData: Metric data structure
   - LLMAnalysisResult: Analysis output
   - MetricsAnalyzer: Metric analysis logic
   - QwenLLMAnalyzer: LLM interface
   - AIPerformanceAnalysisEngine: Main orchestrator
   
   Usage:
   ```python
   from ai_performance_llm_engine import AIPerformanceAnalysisEngine
   engine = AIPerformanceAnalysisEngine()
   result = engine.process_ml_output(record)
   ```

2. example_usage.py
   - 7 complete examples showing how to use the system
   - Run: python3 example_usage.py
   
   Examples:
   - Basic usage with synthetic analysis
   - Detailed single record analysis
   - Threshold and anomaly analysis
   - Full batch processing
   - Database schema and queries
   - Pipeline integration

3. README.md
   - Complete documentation
   - Architecture overview
   - Database integration guide
   - Troubleshooting tips
   - API reference

4. Output Files:
   - LLMAnalysisResults.csv: Main results (CSV format)
   - LLMAnalysisResults.jsonl: Results in JSON Lines format
   - Both contain identical data, different formats

5. Quickstart Guide (this file)
   - Quick setup and testing
   - Next steps and integration guide
    """)


def main():
    """Main entry point"""
    print("""
    
╔════════════════════════════════════════════════════════════════════╗
║                   AI PERFORMANCE INTELLIGENT ENGINE               ║
║              LLM-Based Root Cause Analysis - Quick Start           ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Step 1: Install dependencies
        install_dependencies()
        
        # Step 2: Quick test
        quick_test()
        
        # Step 3: Full batch
        full_batch_process()
        
        # Step 4: Show LLM setup info
        setup_llm()
        
        # Step 5: Show next steps
        show_next_steps()
        
        # Step 6: Show file guide
        show_file_guide()
        
        # Final message
        print_header("✓ QUICK START COMPLETE!")
        
        print("""
Your LLM component is ready to use!

Output Files:
  • LLMAnalysisResults.csv - Main results file
  • LLMAnalysisResults.jsonl - JSON format for databases
  • QuickTest_Results.csv - Quick test results
  
Next: Load these into your database and build dashboards on top!

Questions? Check README.md for detailed documentation.
        """)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
