#!/usr/bin/env python3
"""
Weight Merging Utility - AI Performance Intelligent Engine
Combines the fine-tuned LoRA adapter weights with the base Qwen model.
"""

import os
import argparse
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def merge_lora_weights(base_model_name, adapter_dir, output_dir):
    print("=" * 60)
    print("AI Performance Engine - Model Weight Merger")
    print("=" * 60)
    
    print(f"Base Model: {base_model_name}")
    print(f"LoRA Adapter: {adapter_dir}")
    print(f"Output Directory: {output_dir}\n")
    
    if not os.path.exists(adapter_dir):
        raise FileNotFoundError(f"LoRA Adapter folder not found at {adapter_dir}. Please complete training first.")

    # Check hardware
    if torch.cuda.is_available():
        device_map = "auto"
        torch_dtype = torch.float16
        print("✓ CUDA GPU detected. Loading base model in FP16.")
    else:
        # Load in FP16 on CPU to avoid Apple Silicon unified memory OOM SIGKILL (exit code 137)
        device_map = None
        torch_dtype = torch.float16
        print("✓ Loading base model on CPU in FP16 (Memory optimized).")

    print(f"Step 1/4: Loading base model tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    
    print(f"Step 2/4: Loading base model weights (this may take a few minutes)...")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch_dtype,
        device_map=device_map,
        trust_remote_code=True
    )
    
    print(f"Step 3/4: Loading LoRA adapter & merging weights...")
    model = PeftModel.from_pretrained(base_model, adapter_dir)
    merged_model = model.merge_and_unload()

    print(f"Step 4/4: Saving merged weights to {output_dir}...")
    merged_model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print("\n" + "=" * 60)
    print("✓ Model weights successfully merged!")
    print(f"Location: {os.path.abspath(output_dir)}")
    print("Next step: Convert this model to GGUF format for Ollama.")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Merge LoRA weights with base model")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-1.5B-Instruct",
                        help="Hugging Face base model identifier")
    parser.add_argument("--adapter", type=str, default="qwen-sre-adapter",
                        help="Directory containing the trained adapter")
    parser.add_argument("--output", type=str, default="qwen2.5-1.5b-sre-merged",
                        help="Output directory for the merged model")
    
    args = parser.parse_args()
    
    try:
        merge_lora_weights(
            base_model_name=args.base_model,
            adapter_dir=args.adapter,
            output_dir=args.output
        )
    except Exception as e:
        print(f"\n✗ Weight merging failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
