#!/usr/bin/env python3
"""
SRE Fine-Tuning Pipeline - AI Performance Intelligent Engine
Prepares telemetry training data and executes Qwen LLM fine-tuning using LoRA.
"""

import os
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"
os.environ["HF_HUB_OFFLINE"] = "1"
import sys
import json
import argparse
import pandas as pd
import torch
from datasets import Dataset

# Insert current directory into path to import core logic
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_performance_llm_engine import MetricsAnalyzer

def build_chatml_dataset(jsonl_path):
    """
    Load results and format into ChatML conversation structure for instruction tuning.
    """
    print(f"Loading SRE dataset from {jsonl_path}...")
    if not os.path.exists(jsonl_path):
        raise FileNotFoundError(f"Source dataset not found at {jsonl_path}. Please generate it first.")
        
    records = []
    analyzer = MetricsAnalyzer()
    
    with open(jsonl_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            records.append(json.loads(line))
            
    chat_samples = []
    
    for idx, rec in enumerate(records):
        # We need to reconstruct the raw MetricData from metrics_summary
        metrics_raw = json.loads(rec['metrics_summary'])
        
        # Format metrics to match MetricData structure requirements
        from collections import namedtuple
        MetricDataMock = namedtuple('MetricDataMock', [
            'cpu_usage_rate', 'cpu_throttle_rate', 'cpu_container_vs_node_ratio',
            'memory_usage', 'memory_pressure', 'memory_growth_rate',
            'latency_p95', 'latency_std', 'error_rate', 'failure_streak',
            'restart_flag', 'has_restart', 'disk_io_rate', 'net_throughput'
        ])
        
        # Populate with dataset defaults or actual metrics
        metrics = MetricDataMock(
            cpu_usage_rate=metrics_raw.get('cpu_usage_rate', 0.0),
            cpu_throttle_rate=metrics_raw.get('cpu_throttle_rate', 0.0),
            cpu_container_vs_node_ratio=metrics_raw.get('cpu_container_vs_node_ratio', metrics_raw.get('cpu_usage_rate', 0.0)),
            memory_usage=metrics_raw.get('memory_usage_gb', 0.0) * 1e9,
            memory_pressure=metrics_raw.get('memory_pressure', 0.0),
            memory_growth_rate=metrics_raw.get('memory_growth_rate', 0.0),
            latency_p95=metrics_raw.get('latency_p95', 0.0),
            latency_std=metrics_raw.get('latency_std', 0.0),
            error_rate=metrics_raw.get('error_rate', 0.0),
            failure_streak=metrics_raw.get('failure_streak', 0),
            restart_flag=metrics_raw.get('restart_flag', 0.0),
            has_restart=metrics_raw.get('has_restart', False),
            disk_io_rate=metrics_raw.get('disk_io_rate', 0.0),
            net_throughput=metrics_raw.get('net_throughput', 0.0)
        )
        
        # Compute anomalies
        anomalies, _ = analyzer.identify_anomalies(metrics)
        
        # 1. System system message
        sys_message = "You are an expert DevOps and performance analyst. Analyze the following performance metrics and provide root cause analysis."
        
        # 2. Reconstruct SRE Prompt exactly like core engine
        prompt = f"""You are an expert DevOps and performance analyst. Analyze the following performance metrics and provide root cause analysis.

ML Model Output:
- Severity: {rec.get('ml_severity', 'WARNING')}
- Initial Root Cause: {rec.get('ml_root_cause', 'GENERAL_DEGRADATION')}

Detected Anomalies: {', '.join(anomalies) if anomalies else 'none'}

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

        # 3. Format ground truth output JSON
        target_output = json.dumps({
            "root_cause": rec["root_cause"],
            "confidence": rec["confidence"],
            "evidence": rec["evidence"],
            "affected_component": rec["affected_component"],
            "reasoning": rec["analysis_reasoning"]
        }, indent=2)
        
        # Build ChatML Conversational Structure
        chat_samples.append({
            "messages": [
                {"role": "system", "content": sys_message},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": target_output}
            ]
        })
        
    print(f"✓ Formatted {len(chat_samples)} conversations successfully.")
    return Dataset.from_list(chat_samples)

def run_fine_tuning(dataset, output_dir, base_model, epochs, batch_size, lr):
    """
    Run instruction SFT training using LoRA.
    """
    print("\n" + "="*70)
    print("STARTING PEFT LORA FINE-TUNING PIPELINE")
    print("="*70)
    
    # 1. Install necessary dependencies if needed
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from trl import SFTTrainer
    except ImportError:
        print("Required libraries missing. Please run: pip install transformers peft trl accelerate bitsandbytes datasets")
        return
        
    # Check device availability (MPS for Apple Silicon, CUDA for NVIDIA, CPU as fallback)
    if torch.cuda.is_available():
        device = "cuda"
        torch_dtype = torch.float16
        print("✓ CUDA GPU detected. Training will run on GPU.")
    elif torch.backends.mps.is_available():
        device = "mps"
        torch_dtype = torch.float32
        print("✓ Apple Silicon MPS detected. Training will run on hardware acceleration.")
    else:
        device = "cpu"
        torch_dtype = torch.float32
        print("⚠ Only CPU detected. Training will be extremely slow!")

    print(f"Loading base model and tokenizer: {base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    # Quantization for memory efficiency (QLoRA)
    quantization_config = None
    if device == "cuda":
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch_dtype,
            bnb_4bit_use_double_quant=True
        )
        
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quantization_config,
        torch_dtype=torch_dtype,
        trust_remote_code=True,
        device_map="auto" if device == "cuda" else None
    )
    
    if device == "mps":
        model = model.to("mps")
        
    # Set up LoRA Config
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    # Prepare model for training
    if quantization_config is not None:
        model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    
    # Training Arguments & Trainer Initialization (supporting new SFTConfig and legacy direct TRL kwargs)
    try:
        from trl import SFTConfig
        print("✓ New TRL SFTConfig interface detected. Initializing SFTConfig...")
        
        # SFTConfig configuration dictionary (optimized for lower memory footprint)
        sft_config_kwargs = {
            "output_dir": output_dir,
            "num_train_epochs": epochs,
            "per_device_train_batch_size": batch_size,
            "gradient_accumulation_steps": 4,
            "learning_rate": lr,
            "logging_steps": 5,
            "save_strategy": "epoch",
            "eval_strategy": "no",
            "fp16": (device == "cuda"),
            "optim": "adamw_torch",
            "report_to": "none",
            "packing": False,
            "gradient_checkpointing": True  # Dramatically reduces MPS memory consumption
        }
        
        # Dynamically inspect SFTConfig signature to support both max_seq_length and max_length
        import inspect
        sig = inspect.signature(SFTConfig.__init__)
        if "max_seq_length" in sig.parameters:
            print("  -> Configuring sequence length via 'max_seq_length' (optimized to 512)")
            sft_config_kwargs["max_seq_length"] = 512
        else:
            print("  -> Configuring sequence length via 'max_length' (optimized to 512)")
            sft_config_kwargs["max_length"] = 512
            
        sft_config = SFTConfig(**sft_config_kwargs)
        
        # Dynamically inspect SFTTrainer signature to support both processing_class and tokenizer
        sft_trainer_kwargs = {
            "model": model,
            "train_dataset": dataset,
            "args": sft_config
        }
        
        sig_trainer = inspect.signature(SFTTrainer.__init__)
        if "processing_class" in sig_trainer.parameters:
            print("  -> Configuring tokenizer via 'processing_class'")
            sft_trainer_kwargs["processing_class"] = tokenizer
        else:
            print("  -> Configuring tokenizer via 'tokenizer'")
            sft_trainer_kwargs["tokenizer"] = tokenizer
            
        trainer = SFTTrainer(**sft_trainer_kwargs)
    except ImportError:
        print("✓ Legacy TRL interface detected. Initializing SFTTrainer with direct kwargs...")
        from transformers import TrainingArguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=4,
            learning_rate=lr,
            logging_steps=5,
            save_strategy="epoch",
            eval_strategy="no",
            fp16=(device == "cuda"),
            optim="adamw_torch",
            report_to="none",
            gradient_checkpointing=True
        )
        trainer = SFTTrainer(
            model=model,
            train_dataset=dataset,
            peft_config=peft_config,
            dataset_text_field="messages",
            max_seq_length=512,
            tokenizer=tokenizer,
            args=training_args,
            packing=False
        )
    
    print("Starting training loop...")
    trainer.train()
    
    print(f"✓ Training complete! Saving adapter to {output_dir}")
    trainer.model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print("Done!")

def main():
    parser = argparse.ArgumentParser(description="SRE Fine-Tuning Pipeline for Qwen LLM")
    parser.add_argument("--dataset", type=str, default="LLMAnalysisResults_Full.jsonl",
                        help="Path to target training dataset")
    parser.add_argument("--output-dir", type=str, default="qwen-sre-adapter",
                        help="Directory to save the trained adapter")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-1.5B-Instruct",
                        help="Hugging Face base model identifier")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size per device")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    
    args = parser.parse_args()
    
    try:
        # 1. Format dataset
        dataset = build_chatml_dataset(args.dataset)
        
        # 2. Run PEFT fine-tuning
        run_fine_tuning(
            dataset=dataset,
            output_dir=args.output_dir,
            base_model=args.base_model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr
        )
    except Exception as e:
        print(f"\n✗ Fine-Tuning failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
