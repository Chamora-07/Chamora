"""
AI Performance Intelligent Engine - Fine-tuned LLM Component
This module processes ML model outputs through a fine-tuned Qwen LLM to generate
root cause analysis, confidence scores, evidence, and affected components.
"""

import json
import csv
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
import subprocess
import sys

# For local Qwen LLM (ollama alternative)
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


@dataclass
class MetricData:
    """Parsed metric data from ML model evidence"""
    error_rate: float
    has_restart: bool
    latency_p95: float
    latency_std: float
    disk_io_rate: float
    memory_usage: float
    restart_flag: float
    cpu_usage_rate: float
    failure_streak: int
    net_throughput: float
    memory_pressure: float
    memory_growth_rate: float
    cpu_container_vs_node_ratio: float


@dataclass
class LLMAnalysisResult:
    """Output structure from LLM analysis"""
    id: str
    application_id: int
    config_id: int
    window_timestamp: str
    ml_severity: str
    ml_root_cause: str
    root_cause: str
    confidence: float
    evidence: str
    affected_component: str
    metrics_summary: Dict[str, Any]
    analysis_reasoning: str
    created_at: str


class MetricsAnalyzer:
    """Analyze metrics and identify thresholds"""
    
    # Default thresholds (can be tuned based on your SLA)
    THRESHOLDS = {
        'latency_p95': 0.05,  # seconds
        'error_rate': 0.01,  # 1%
        'cpu_usage_rate': 0.85,  # 85%
        'memory_usage': 900000000,  # 900MB
        'memory_pressure': 0.8,
        'memory_growth_rate': 50000000,  # 50MB/s growth
        'disk_io_rate': 0.8,
        'cpu_container_vs_node_ratio': 0.9,
        'failure_streak': 5
    }
    
    @staticmethod
    def parse_metrics(evidence_str: str) -> MetricData:
        """Parse evidence JSON string into MetricData"""
        try:
            metrics_dict = json.loads(evidence_str)
            if "raw_values" in metrics_dict and isinstance(metrics_dict["raw_values"], dict):
                metrics_dict = metrics_dict["raw_values"]
            import dataclasses
            valid_keys = {f.name for f in dataclasses.fields(MetricData)}
            filtered_dict = {k: v for k, v in metrics_dict.items() if k in valid_keys}
            if 'has_restart' not in filtered_dict:
                filtered_dict['has_restart'] = False
            return MetricData(**filtered_dict)
        except Exception:
            return None
    
    @staticmethod
    def identify_anomalies(metrics: MetricData) -> Tuple[List[str], Dict[str, float]]:
        """Identify which metrics are anomalous"""
        anomalies = []
        severity_scores = {}
        
        if metrics.latency_p95 > MetricsAnalyzer.THRESHOLDS['latency_p95']:
            anomalies.append('high_latency')
            severity_scores['latency_p95'] = metrics.latency_p95 / MetricsAnalyzer.THRESHOLDS['latency_p95']
        
        if metrics.error_rate > MetricsAnalyzer.THRESHOLDS['error_rate']:
            anomalies.append('high_error_rate')
            severity_scores['error_rate'] = metrics.error_rate / MetricsAnalyzer.THRESHOLDS['error_rate']
        
        if metrics.cpu_usage_rate > MetricsAnalyzer.THRESHOLDS['cpu_usage_rate']:
            anomalies.append('high_cpu_usage')
            severity_scores['cpu_usage_rate'] = metrics.cpu_usage_rate / MetricsAnalyzer.THRESHOLDS['cpu_usage_rate']
        
        if metrics.memory_usage > MetricsAnalyzer.THRESHOLDS['memory_usage']:
            anomalies.append('high_memory_usage')
            severity_scores['memory_usage'] = metrics.memory_usage / MetricsAnalyzer.THRESHOLDS['memory_usage']
        
        if metrics.memory_pressure > MetricsAnalyzer.THRESHOLDS['memory_pressure']:
            anomalies.append('memory_pressure_high')
            severity_scores['memory_pressure'] = metrics.memory_pressure / MetricsAnalyzer.THRESHOLDS['memory_pressure']
        
        if abs(metrics.memory_growth_rate) > MetricsAnalyzer.THRESHOLDS['memory_growth_rate']:
            anomalies.append('memory_leak_indicator')
            severity_scores['memory_growth_rate'] = abs(metrics.memory_growth_rate) / MetricsAnalyzer.THRESHOLDS['memory_growth_rate']
        
        if metrics.disk_io_rate > MetricsAnalyzer.THRESHOLDS['disk_io_rate']:
            anomalies.append('high_disk_io')
            severity_scores['disk_io_rate'] = metrics.disk_io_rate / MetricsAnalyzer.THRESHOLDS['disk_io_rate']
        
        if metrics.cpu_container_vs_node_ratio > MetricsAnalyzer.THRESHOLDS['cpu_container_vs_node_ratio']:
            anomalies.append('cpu_contention')
            severity_scores['cpu_container_vs_node_ratio'] = metrics.cpu_container_vs_node_ratio / MetricsAnalyzer.THRESHOLDS['cpu_container_vs_node_ratio']
        
        if metrics.failure_streak > MetricsAnalyzer.THRESHOLDS['failure_streak']:
            anomalies.append('repeated_failures')
            severity_scores['failure_streak'] = metrics.failure_streak / MetricsAnalyzer.THRESHOLDS['failure_streak']
        
        if metrics.has_restart or metrics.restart_flag > 0:
            anomalies.append('container_restart')
            severity_scores['restart_flag'] = 1.0
        
        return anomalies, severity_scores
    
    @staticmethod
    def correlate_metrics(metrics: MetricData, anomalies: List[str]) -> Dict[str, Any]:
        """Correlate anomalies to identify root causes"""
        correlations = {
            'memory_issue': False,
            'cpu_issue': False,
            'io_issue': False,
            'application_issue': False,
            'infrastructure_issue': False
        }
        
        memory_anomalies = {'high_memory_usage', 'memory_pressure_high', 'memory_leak_indicator'}
        cpu_anomalies = {'high_cpu_usage', 'cpu_contention'}
        io_anomalies = {'high_disk_io'}
        restart_anomalies = {'container_restart', 'repeated_failures'}
        
        if any(a in anomalies for a in memory_anomalies):
            correlations['memory_issue'] = True
        
        if any(a in anomalies for a in cpu_anomalies):
            correlations['cpu_issue'] = True
        
        if any(a in anomalies for a in io_anomalies):
            correlations['io_issue'] = True
        
        if any(a in anomalies for a in restart_anomalies):
            correlations['infrastructure_issue'] = True
        
        if 'high_latency' in anomalies or 'high_error_rate' in anomalies:
            correlations['application_issue'] = True
        
        return correlations


class QwenLLMAnalyzer:
    """Interface with Qwen LLM for root cause analysis"""
    
    def __init__(self, model_name: str = "qwen:4b", api_url: str = "http://localhost:11434"):
        """
        Initialize Qwen LLM analyzer
        
        Args:
            model_name: Qwen model variant (default: qwen:4b)
            api_url: Ollama API endpoint
        """
        self.model_name = model_name
        self.api_url = api_url
        self.available = self._check_llm_availability()
    
    def _check_llm_availability(self) -> bool:
        """Check if LLM service is available"""
        try:
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={"model": self.model_name, "prompt": "test", "stream": False},
                timeout=30
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Warning: LLM service not available ({e}).")
            return False
    
    def analyze_with_llm(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Qwen LLM with structured prompt for root cause analysis
        """
        if not self.available:
            raise RuntimeError("LLM service is not available. Please ensure Ollama is running and qwen:4b is loaded.")
        
        prompt = self._build_prompt(context)
        
        try:
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": 300
                    }
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result_text = response.json().get('response', '')
                return self._parse_llm_response(result_text, context)
            else:
                raise RuntimeError(f"Ollama server returned status code {response.status_code}: {response.text}")
        except Exception as e:
            print(f"LLM call failed: {e}")
            raise e
    
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build structured prompt for LLM"""
        metrics = context['metrics']
        anomalies = context['anomalies']
        ml_severity = context['ml_severity']
        ml_root_cause = context['ml_root_cause']
        
        prompt = f"""You are an expert DevOps and performance analyst. Analyze the following performance metrics and provide root cause analysis.

ML Model Output:
- Severity: {ml_severity}
- Initial Root Cause: {ml_root_cause}

Detected Anomalies: {', '.join(anomalies)}

System Metrics:
- CPU Usage Rate: {metrics.cpu_usage_rate:.4f}
- Memory Usage: {metrics.memory_usage / 1e9:.2f} GB
- Memory Pressure: {metrics.memory_pressure:.4f}
- Memory Growth Rate: {metrics.memory_growth_rate / 1e6:.2f} MB/s
- Latency P95: {metrics.latency_p95:.4f}s
- Error Rate: {metrics.error_rate:.4f}
- Disk I/O Rate: {metrics.disk_io_rate:.4f}
- Network Throughput: {metrics.net_throughput:.2f} Mbps
- CPU Container vs Node Ratio: {metrics.cpu_container_vs_node_ratio:.4f}
- Failure Streak: {metrics.failure_streak}
- Container Restarts: {metrics.has_restart}

Task: Provide a JSON response with:
1. "root_cause": specific root cause (one of: MEMORY_LEAK, CPU_SATURATION, NETWORK_BOTTLENECK, APPLICATION_BUG, RESOURCE_CONTENTION, GC_PRESSURE, IO_BOTTLENECK, CONFIGURATION_ISSUE, UNKNOWN)
2. "confidence": confidence score (0.0-1.0)
3. "evidence": brief explanation with key metrics supporting the conclusion
4. "affected_component": which component (API_SERVER, CACHE, DATABASE, MESSAGE_QUEUE, STORAGE, NETWORK, SCHEDULER, APPLICATION)
5. "reasoning": detailed analysis

Format as JSON only."""
        
        return prompt
    
    def _parse_llm_response(self, response_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM response"""
        try:
            # Extract the first balanced JSON block { ... } to handle conversational repetition
            text = response_text.strip()
            json_str = ""
            brace_count = 0
            start_idx = -1
            
            for i, char in enumerate(text):
                if char == '{':
                    if brace_count == 0:
                        start_idx = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_idx != -1:
                        json_str = text[start_idx:i+1]
                        break
            
            if not json_str:
                # Fallback to standard substring matching if braces are unbalanced
                json_start = text.find('{')
                json_end = text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = text[json_start:json_end]
            
            if not json_str:
                raise ValueError("No JSON block found in response")
                
            parsed = json.loads(json_str)
            
            # Map root cause mapping defaults
            root_cause = str(parsed.get('root_cause', '')).strip().upper()
            
            # Smart SRE Keyword Fallback Heuristic
            if not root_cause or root_cause == 'UNKNOWN' or root_cause == '':
                reasoning_lower = str(parsed.get('reasoning', '')).lower()
                evidence_lower = str(parsed.get('evidence', '')).lower()
                combined_text = reasoning_lower + " " + evidence_lower
                
                if any(x in combined_text for x in ['config', 'mismatch', 'probe', 'restart', 'loop', 'startup']):
                    root_cause = 'CONFIGURATION_ISSUE'
                elif any(x in combined_text for x in ['leak', 'growth', 'pressure', 'oom']):
                    root_cause = 'MEMORY_LEAK'
                elif any(x in combined_text for x in ['cpu', 'saturation', 'throttle', 'load']):
                    root_cause = 'CPU_SATURATION'
                elif any(x in combined_text for x in ['network', 'throughput', 'bandwidth', 'packet']):
                    root_cause = 'NETWORK_BOTTLENECK'
                elif any(x in combined_text for x in ['bug', 'exception', 'crash', 'nullpointer']):
                    root_cause = 'APPLICATION_BUG'
                elif any(x in combined_text for x in ['contention', 'lock', 'thread', 'waiting']):
                    root_cause = 'RESOURCE_CONTENTION'
                elif any(x in combined_text for x in ['gc', 'garbage collection', 'heap']):
                    root_cause = 'GC_PRESSURE'
                elif any(x in combined_text for x in ['disk', 'io', 'i/o', 'write', 'read']):
                    root_cause = 'IO_BOTTLENECK'
                else:
                    root_cause = 'UNKNOWN'
                
            return {
                'root_cause': root_cause,
                'confidence': min(1.0, max(0.0, float(parsed.get('confidence', 0.5)))),
                'evidence': parsed.get('evidence', ''),
                'affected_component': parsed.get('affected_component', 'APPLICATION'),
                'reasoning': parsed.get('reasoning', '')
            }
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse LLM response: {e}")
            raise ValueError(f"Could not parse valid JSON from LLM output: {response_text}") from e


class AIPerformanceAnalysisEngine:
    """Main engine orchestrating the analysis pipeline"""
    
    def __init__(self, model_name: str = "qwen:4b", api_url: str = "http://localhost:11434"):
        """
        Initialize the analysis engine
        """
        self.metrics_analyzer = MetricsAnalyzer()
        self.llm_analyzer = QwenLLMAnalyzer(model_name=model_name, api_url=api_url)
        self.results = []
    
    def process_ml_output(self, ml_record: Dict[str, Any]) -> LLMAnalysisResult:
        """
        Process a single ML model output record
        
        Args:
            ml_record: ML model output row
            
        Returns:
            LLMAnalysisResult with complete analysis
        """
        # Parse metrics from evidence
        metrics = self.metrics_analyzer.parse_metrics(ml_record['evidence'])
        
        if metrics is None:
            return self._create_error_result(ml_record, "Failed to parse metrics")
        
        # Identify anomalies
        anomalies, severity_scores = self.metrics_analyzer.identify_anomalies(metrics)
        
        # Correlate metrics
        correlations = self.metrics_analyzer.correlate_metrics(metrics, anomalies)
        
        # Build context for LLM
        context = {
            'metrics': metrics,
            'anomalies': anomalies,
            'severity_scores': severity_scores,
            'correlations': correlations,
            'ml_severity': ml_record.get('severity', 'WARNING'),
            'ml_root_cause': ml_record.get('root_cause', 'GENERAL_DEGRADATION'),
        }
        
        # Analyze with LLM
        try:
            llm_analysis = self.llm_analyzer.analyze_with_llm(context)
        except Exception as e:
            return self._create_error_result(ml_record, f"LLM Analysis error: {str(e)}")
        
        # Create result
        result = LLMAnalysisResult(
            id=ml_record['id'],
            application_id=ml_record['application_id'],
            config_id=ml_record['config_id'],
            window_timestamp=ml_record['window_timestamp'],
            ml_severity=ml_record.get('severity', 'WARNING'),
            ml_root_cause=ml_record.get('root_cause', 'GENERAL_DEGRADATION'),
            root_cause=llm_analysis['root_cause'],
            confidence=llm_analysis['confidence'],
            evidence=llm_analysis['evidence'],
            affected_component=llm_analysis['affected_component'],
            metrics_summary={
                'cpu_usage_rate': round(metrics.cpu_usage_rate, 4),
                'memory_usage_gb': round(metrics.memory_usage / 1e9, 2),
                'memory_pressure': round(metrics.memory_pressure, 4),
                'latency_p95': round(metrics.latency_p95, 4),
                'error_rate': round(metrics.error_rate, 4),
            },
            analysis_reasoning=llm_analysis['reasoning'],
            created_at=datetime.utcnow().isoformat()
        )
        
        return result
    
    def _create_error_result(self, ml_record: Dict[str, Any], error_message: str = "Failed to parse metrics") -> LLMAnalysisResult:
        """Create error result when metrics parsing or LLM fails"""
        return LLMAnalysisResult(
            id=ml_record['id'],
            application_id=ml_record['application_id'],
            config_id=ml_record['config_id'],
            window_timestamp=ml_record['window_timestamp'],
            ml_severity=ml_record.get('severity', 'WARNING'),
            ml_root_cause=ml_record.get('root_cause', 'GENERAL_DEGRADATION'),
            root_cause='UNKNOWN',
            confidence=0.0,
            evidence=error_message,
            affected_component='APPLICATION',
            metrics_summary={},
            analysis_reasoning='Analysis failed or LLM not available',
            created_at=datetime.utcnow().isoformat()
        )
    
    def process_file(self, input_csv_path: str, output_csv_path: str, limit: int = None) -> int:
        """
        Process entire CSV file and save results
        
        Args:
            input_csv_path: Path to ML output CSV
            output_csv_path: Path to save LLM analysis results
            limit: Maximum records to process (for testing)
            
        Returns:
            Number of records processed
        """
        records_processed = 0
        
        # Read CSV
        df = pd.read_csv(input_csv_path)
        
        # Limit records if specified
        if limit:
            df = df.head(limit)
        
        print(f"Processing {len(df)} records...")
        
        # Process each record
        for idx, row in df.iterrows():
            try:
                record_dict = row.to_dict()
                result = self.process_ml_output(record_dict)
                self.results.append(result)
                records_processed += 1
                
                if (idx + 1) % 10 == 0:
                    print(f"  Processed {idx + 1}/{len(df)} records...")
            
            except Exception as e:
                print(f"Error processing record {idx}: {e}")
                continue
        
        # Save results
        self._save_results(output_csv_path)
        print(f"\nResults saved to {output_csv_path}")
        
        return records_processed
    
    def _save_results(self, output_path: str):
        """Save analysis results to CSV"""
        output_data = []
        
        for result in self.results:
            output_data.append({
                'id': result.id,
                'application_id': result.application_id,
                'config_id': result.config_id,
                'window_timestamp': result.window_timestamp,
                'ml_severity': result.ml_severity,
                'ml_root_cause': result.ml_root_cause,
                'root_cause': result.root_cause,
                'confidence': result.confidence,
                'affected_component': result.affected_component,
                'evidence': result.evidence,
                'metrics_summary': json.dumps(result.metrics_summary),
                'analysis_reasoning': result.analysis_reasoning,
                'created_at': result.created_at,
            })
        
        output_df = pd.DataFrame(output_data)
        output_df.to_csv(output_path, index=False)
        
        # Also save as JSON for database ingestion
        json_path = output_path.replace('.csv', '.jsonl')
        with open(json_path, 'w') as f:
            for row in output_data:
                f.write(json.dumps(row) + '\n')
        
        print(f"Also saved JSONL format to {json_path}")
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of analysis"""
        if not self.results:
            return {}
        
        root_causes = [r.root_cause for r in self.results]
        components = [r.affected_component for r in self.results]
        confidences = [r.confidence for r in self.results]
        
        # Convert to native Python types for JSON serialization
        root_cause_dist = {str(k): int(v) for k, v in pd.Series(root_causes).value_counts().items()}
        component_dist = {str(k): int(v) for k, v in pd.Series(components).value_counts().items()}
        
        return {
            'total_records': int(len(self.results)),
            'root_cause_distribution': root_cause_dist,
            'affected_component_distribution': component_dist,
            'avg_confidence': float(round(np.mean(confidences), 3)),
            'min_confidence': float(round(min(confidences), 3)),
            'max_confidence': float(round(max(confidences), 3)),
        }


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Performance Analysis Engine')
    parser.add_argument('--input', type=str, default='/mnt/user-data/uploads/MLOutput.csv',
                       help='Input ML output CSV file')
    parser.add_argument('--output', type=str, default='/mnt/user-data/outputs/LLMAnalysisResults.csv',
                       help='Output analysis results CSV file')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of records to process')
    parser.add_argument('--model-name', type=str, default='qwen:4b-instruct',
                       help='Qwen model variant (default: qwen:4b-instruct)')
    parser.add_argument('--api-url', type=str, default='http://localhost:11434',
                       help='Ollama API endpoint')
    
    args = parser.parse_args()
    
    # Initialize engine
    engine = AIPerformanceAnalysisEngine(model_name=args.model_name, api_url=args.api_url)
    
    # Process file
    processed = engine.process_file(args.input, args.output, limit=args.limit)
    
    # Print summary
    print("\n" + "="*60)
    print("ANALYSIS SUMMARY")
    print("="*60)
    
    stats = engine.get_summary_stats()
    print(json.dumps(stats, indent=2))
    
    print(f"\n✓ Successfully processed {processed} records")


if __name__ == '__main__':
    main()
