# Script Model Fine-Tuning Guide

> A complete guide to fine-tuning your own short drama script generation model — from model selection to production deployment.

---

## 1. Why Fine-Tune?

Generic LLMs (DeepSeek, GPT-4) are trained on broad internet data. They lack:
- **Short drama format awareness**: episode structure, cliffhanger patterns, dialogue density
- **Genre-specific style**: romance vs thriller have fundamentally different pacing and dialogue
- **Platform compliance**: 红果短剧 requires specific episode length, hook placement, audio-visual alignment
- **Cost efficiency**: fine-tuned 7B model costs ~$0.02/script vs $0.15/script for GPT-4 API

A fine-tuned model produces scripts that are **2-3× closer to publishable quality** compared to prompt-engineered generic models.

---

## 2. Model Selection

### 2.1 Base Model Comparison (2026 Q3)

| Model | Size | VRAM (FP16) | VRAM (QLoRA) | Script Quality | Cost/1M tokens | Recommendation |
|-------|------|-------------|-------------|----------------|----------------|----------------|
| **Qwen2.5-7B-Instruct** | 7B | 14GB | 6GB | ★★★★☆ | $0.15 | ⭐ Best value |
| Qwen2.5-14B-Instruct | 14B | 28GB | 12GB | ★★★★★ | $0.40 | Best quality |
| Qwen2.5-1.5B-Instruct | 1.5B | 3GB | 2GB | ★★★☆☆ | $0.05 | Lightweight/edge |
| DeepSeek-V3 (API only) | 671B MoE | — | — | ★★★★★ | $0.50 | Best via API |
| Yi-1.5-9B-Chat | 9B | 18GB | 8GB | ★★★★☆ | $0.20 | Good alternative |
| GLM-4-9B-Chat | 9B | 18GB | 8GB | ★★★★☆ | $0.20 | Strong Chinese |

**Recommendation for most teams**: Start with **Qwen2.5-7B-Instruct + QLoRA**. It hits the sweet spot of quality, cost, and hardware requirements.

### 2.2 Why Qwen2.5 Over Others?

1. **Chinese-native**: trained on massive Chinese corpus, understands 古风/玄幻/都市 nuances
2. **Strong instruction following**: ChatML format, reliable structured output
3. **Active ecosystem**: QLoRA/LoRA tooling, vLLM deployment, community recipes
4. **Apache 2.0 license**: no restrictions on commercial use

---

## 3. Data Preparation

### 3.1 Data Requirements

| Tier | Scripts Needed | Expected Quality Gain | Training Time (1×A100) |
|------|---------------|----------------------|------------------------|
| Minimal | 500-1,000 | +15-20% | 4-8 hours |
| Good | 5,000-10,000 | +25-35% | 1-2 days |
| Production | 50,000+ | +40-50% | 3-5 days |

### 3.2 Data Format

Each training sample should be in ChatML format with system prompt + user request + assistant response:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "你是专业短剧编剧。输出格式：每集以「第N集」开头，包含场景描述、角色对白、动作指示。每集结尾必须有悬念钩子。"
    },
    {
      "role": "user",
      "content": "创作一部短剧。\n主题：重生复仇\n风格：古装\n长度：短篇(10集)\n大纲：修真者重生回到百年前，带着前世记忆逆天改命..."
    },
    {
      "role": "assistant",
      "content": "第一集\n\n【场景一：青云峰 - 黎明】\n△晨雾弥漫，一个少年盘坐在悬崖边...\n...(完整剧本)"
    }
  ]
}
```

### 3.3 Data Sources

| Source | Quality | Scale | How to Collect |
|--------|---------|-------|---------------|
| **Platform generated scripts** | ★★★★☆ | 100s-1000s | Export from Short Drama Platform database |
| **Public short drama scripts** | ★★★☆☆ | 1000s | Web scraping (with copyright check) |
| **Licensed script databases** | ★★★★★ | 10,000s | Purchase from script marketplaces |
| **LLM-generated + curated** | ★★★☆☆ | Unlimited | Generate with GPT-4, manually curate top 20% |
| **Human-written scripts** | ★★★★★ | 100s | Hire scriptwriters, use as gold standard |

### 3.4 Data Cleaning Pipeline

```python
# data_cleaning.py
import json
import re
from typing import List, Dict

def clean_script_sample(sample: Dict) -> Dict | None:
    """Validate and clean a single training sample."""
    content = sample["messages"][-1]["content"]

    # 1. Length filter: scripts should be 500-8000 chars
    if len(content) < 500 or len(content) > 8000:
        return None

    # 2. Episode marker check: must have 第N集
    if not re.search(r"第\s*[一二三四五六七八九十百千\d]+\s*集", content):
        return None

    # 3. Dialogue density: should have character dialogue (角色名：...)
    dialogue_lines = len(re.findall(r"[^\s]{2,4}[：:]", content))
    total_lines = content.count("\n") + 1
    dialogue_ratio = dialogue_lines / max(total_lines, 1)
    if dialogue_ratio < 0.1 or dialogue_ratio > 0.8:
        return None

    # 4. Content safety: no sensitive keywords
    sensitive = ["色情", "赌博", "毒品", "违法"]
    if any(kw in content for kw in sensitive):
        return None

    # 5. Deduplication: remove near-identical samples
    # (use MinHash or embedding similarity)

    return sample


def prepare_dataset(raw_samples: List[Dict]) -> List[Dict]:
    """Clean and prepare dataset for training."""
    cleaned = []
    for sample in raw_samples:
        result = clean_script_sample(sample)
        if result:
            cleaned.append(result)
    print(f"Cleaned: {len(cleaned)}/{len(raw_samples)} samples kept "
          f"({100*len(cleaned)/len(raw_samples):.1f}%)")
    return cleaned
```

### 3.5 Data Augmentation

Boost your dataset 2-3× with these techniques:

```
1. Style Transfer:
   Original (古装) → Rewrite as 都市风格 (keep plot, change setting)

2. Length Variation:
   Original (中篇 20集) → Summarize to 短篇 5集
   Original (短篇) → Expand to 中篇

3. Character Swap:
   Original(男主视角) → Rewrite from 女主视角

4. Cliffhanger Enhancement:
   LLM rewrites episode endings to add stronger hooks

5. Dialogue Enrichment:
   LLM adds emotional annotations: 角色名：(愤怒)台词 → 角色名：(强忍愤怒)台词
```

---

## 4. Fine-Tuning Algorithms

### 4.1 Method Comparison

| Method | VRAM Required | Training Speed | Quality | Use Case |
|--------|--------------|----------------|---------|----------|
| **QLoRA** (4-bit) | 6GB (7B) / 12GB (14B) | Fast (1×A100, 8h) | ★★★★☆ | Best for most teams |
| **LoRA** (16-bit) | 14GB (7B) / 28GB (14B) | Moderate (1×A100, 16h) | ★★★★☆ | Slightly better than QLoRA |
| **Full Fine-Tune** | 56GB (7B) / 112GB (14B) | Slow (4×A100, 48h) | ★★★★★ | Maximum quality |
| **DPO** (RLHF alternative) | Same as QLoRA | +2h on top | ★★★★★ | Preference alignment |

### 4.2 QLoRA Fine-Tuning Code

```python
# train_qlora.py
import torch
from datasets import Dataset, load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# ── Configuration ──
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
OUTPUT_DIR = "./script-model-qlora"
DATASET_PATH = "./data/scripts.jsonl"

# ── 4-bit Quantization Config ──
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

# ── Load Model ──
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token

# ── Prepare for QLoRA ──
model = prepare_model_for_kbit_training(model)

# ── LoRA Config ──
lora_config = LoraConfig(
    r=16,               # Rank — higher = more capacity, slower
    lora_alpha=32,      # Scaling factor
    target_modules=[     # Qwen2.5 attention layers
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# Output: trainable params: 41,943,040 || all params: 7,656,894,464 || trainable%: 0.55%

# ── Load Dataset ──
dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
dataset = dataset.train_test_split(test_size=0.05)

def format_chatml(example):
    """Format sample as ChatML string."""
    msgs = example["messages"]
    text = ""
    for msg in msgs:
        text += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
    text += "<|im_start|>assistant\n"  # Let model generate
    return {"text": text}

dataset = dataset.map(format_chatml)

# ── Training Arguments ──
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,     # Effective batch = 4×4 = 16
    num_train_epochs=3,
    learning_rate=2e-4,
    warmup_ratio=0.03,
    lr_scheduler_type="cosine",
    logging_steps=10,
    save_steps=500,
    eval_steps=500,
    save_total_limit=3,
    bf16=True,
    gradient_checkpointing=True,
    report_to="wandb",                 # Track with Weights & Biases
    run_name="script-model-qlora-v1",
)

# ── Train ──
trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
    eval_dataset=dataset["test"],
    tokenizer=tokenizer,
    max_seq_length=4096,
    packing=True,                      # Pack multiple samples into one sequence
)

trainer.train()

# ── Save ──
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

# ── Merge LoRA weights (optional, for vLLM deployment) ──
# from peft import PeftModel
# merged = model.merge_and_unload()
# merged.save_pretrained(f"{OUTPUT_DIR}-merged")
```

### 4.3 Advanced: DPO Preference Alignment

After QLoRA, add Direct Preference Optimization for quality alignment:

```python
# train_dpo.py — run AFTER QLoRA
from trl import DPOTrainer, DPOConfig

# Prepare preference pairs:
#   chosen: high-quality script (rated 8+ by human/judge)
#   rejected: low-quality script (rated <6)
dpo_config = DPOConfig(
    output_dir="./script-model-dpo",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    num_train_epochs=1,
    learning_rate=5e-5,
    beta=0.1,              # Temperature for preference strength
    max_length=4096,
    max_prompt_length=2048,
)

dpo_trainer = DPOTrainer(
    model=model,
    ref_model=model,       # Reference = current QLoRA model
    args=dpo_config,
    train_dataset=dpo_dataset,
    tokenizer=tokenizer,
)

dpo_trainer.train()
model.save_pretrained("./script-model-dpo-final")
```

---

## 5. Evaluation

### 5.1 Automated Evaluation

```python
# eval_model.py
def evaluate_model(model, tokenizer, test_prompts: List[str]) -> Dict:
    """Evaluate fine-tuned model on test prompts."""
    from app.services.quality_judge import QualityJudge

    judge = QualityJudge(llm=base_llm)  # Use a separate LLM as judge
    results = []

    for prompt in test_prompts:
        # Generate with fine-tuned model
        inputs = tokenizer.apply_chat_template(
            prompt, return_tensors="pt").to("cuda")
        outputs = model.generate(inputs, max_new_tokens=4096,
                                 temperature=0.7, do_sample=True)
        script = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Judge
        report = await judge.judge_script(script)
        results.append(report.to_dict())

    # Aggregate
    scores = {
        "avg_score": sum(r["total_score"] for r in results) / len(results),
        "pass_rate": sum(1 for r in results if r["verdict"] == "pass") / len(results),
        "coherence": sum(r["scores"]["coherence"] for r in results) / len(results),
        "consistency": sum(r["scores"]["character_consistency"] for r in results) / len(results),
        "dialogue": sum(r["scores"]["dialogue_naturalness"] for r in results) / len(results),
    }
    return scores
```

### 5.2 A/B Testing Against Baseline

```python
# Compare fine-tuned vs base model on the same prompts
baseline_scores = evaluate_model(base_model, tokenizer, test_prompts)
finetuned_scores = evaluate_model(finetuned_model, tokenizer, test_prompts)

print(f"Baseline:   {baseline_scores['avg_score']:.1f}")
print(f"Fine-tuned: {finetuned_scores['avg_score']:.1f}")
print(f"Improvement: +{(finetuned_scores['avg_score'] - baseline_scores['avg_score']):.1f} points")
```

---

## 6. Cost Estimation

### 6.1 Training Cost (Cloud GPU)

| Configuration | GPU | Time | Cost (AWS) | Cost (AutoDL CN) |
|--------------|-----|------|-----------|-----------------|
| QLoRA 7B, 1K scripts | 1×A100 40GB | 8h | ~$25 | ~¥50 |
| QLoRA 7B, 10K scripts | 1×A100 40GB | 2 days | ~$150 | ~¥300 |
| Full FT 14B, 50K scripts | 4×A100 80GB | 3 days | ~$2,500 | ~¥5,000 |
| DPO (after QLoRA) | 1×A100 40GB | +2h | ~$8 | ~¥15 |

### 6.2 Inference Cost Comparison

| Model | Cost/Script | Scripts/$1 |
|-------|------------|------------|
| GPT-4 API | $0.15 | 6.7 |
| DeepSeek API | $0.05 | 20 |
| **Fine-tuned 7B (vLLM)** | **$0.02** | **50** |
| Fine-tuned 14B (vLLM) | $0.05 | 20 |
| Fine-tuned 1.5B (vLLM) | $0.005 | 200 |

### 6.3 ROI Calculation

```
Assumption: 10,000 scripts/month generated

Monthly Cost:
  DeepSeek API: 10,000 × $0.05 = $500/month
  Fine-tuned 7B: 10,000 × $0.02 = $200/month

Training Cost (one-time):
  QLoRA 7B, 5K scripts: ~$80

Break-even: $80 / ($500 - $200) = 0.27 months ≈ 8 days

After 8 days, the fine-tuned model saves $300/month forever.
```

---

## 7. Production Deployment

### 7.1 vLLM Serving

```yaml
# k8s/script-finetune/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: script-model-vllm
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: vllm
          image: vllm/vllm-openai:latest
          args:
            - "--model"
            - "/models/script-model-qlora-merged"
            - "--max-model-len"
            - "8192"
            - "--gpu-memory-utilization"
            - "0.85"
          ports:
            - containerPort: 8000
          resources:
            limits: { "nvidia.com/gpu": "1" }
          volumeMounts:
            - name: models
              mountPath: /models
      volumes:
        - name: models
          persistentVolumeClaim:
            claimName: script-models
```

### 7.2 Integration with ModelRouter

```python
# In .env:
VLLM_API_BASE=http://script-model-vllm:8000/v1
VLLM_SMALL_MODEL=/models/script-model-qlora-merged

# The existing ModelRouter auto-detects vLLM when VLLM_API_BASE is set.
# Fine-tuned model becomes the default for script generation.
```

### 7.3 Continuous Fine-Tuning Pipeline

```
Every week:
  1. Export new scripts from MySQL (WHERE created_at > last_week)
  2. Human/LLM quality filter (keep scripts rated 7+)
  3. Merge with existing dataset → deduplicate
  4. Fine-tune from previous checkpoint (not from scratch)
  5. A/B test against current production model
  6. If wins → promote to production
  7. Archive previous model version
```

---

## 8. Quick Start Checklist

```
□ 1. Collect 1,000+ script samples in ChatML format → data/scripts.jsonl
□ 2. Run clean_script_sample() to filter bad samples
□ 3. Set MODEL_NAME in train_qlora.py
□ 4. Run: python train_qlora.py  (1×A100, ~8h for 1K samples)
□ 5. Evaluate: python eval_model.py
□ 6. If score > baseline + 5 points → proceed
□ 7. Merge LoRA: python merge_lora.py
□ 8. Deploy: kubectl apply -f k8s/deployment.yaml
□ 9. Update .env: VLLM_API_BASE=http://script-model-vllm:8000/v1
□ 10. A/B test for 1 week → full rollout
```

---

## 9. References

- [Qwen2.5 Technical Report](https://arxiv.org/abs/2409.12186)
- [QLoRA: Efficient Finetuning of Quantized LLMs](https://arxiv.org/abs/2305.14314)
- [DPO: Direct Preference Optimization](https://arxiv.org/abs/2305.18290)
- [vLLM: Easy, Fast, and Cheap LLM Serving](https://arxiv.org/abs/2309.06180)
- [HuggingFace TRL (Transformer Reinforcement Learning)](https://github.com/huggingface/trl)
- [Axolotl: Fine-Tuning Framework](https://github.com/OpenAccess-AI-Collective/axolotl)

---

*Document version: 1.0 | Last updated: 2026-07-23*
