---
title: "Gemma4-31Bを日本語エージェントコーダーに特化させた — QLoRAファインチューニングとベンチマーク結果"
emoji: "🔧"
type: "tech"
topics: ["gemma4", "qlora", "finetuning", "claudecode", "llm"]
published: true
---

## はじめに

Google の Gemma4-31B-IT を QLoRA でファインチューニングし、**日本語でのエージェント型コーディング**に特化したモデルを作成しました。

目的は Claude Code のローカルサブエージェントとして使うこと。API トークンを消費せず、ファイル探索・コードレビュー・テスト実行などのルーチン作業をローカル LLM に委譲します。

**モデル**: [Tsunamayo7/gemma4-31b-ja-agent-coder](https://huggingface.co/Tsunamayo7/gemma4-31b-ja-agent-coder)

## ベンチマーク比較

12 カテゴリで学習前後を比較しました。各基準 0-1 のスコアをカテゴリ平均（10 点満点）で評価。

| カテゴリ | ベース | ファインチューン後 | 差分 |
|:--|:--:|:--:|:--:|
| ReAct Tool Call | 10.0 | **10.0** | — |
| Function Calling | 8.0 | **10.0** | +2.0 |
| Multi-step ReAct | 8.0 | **10.0** | +2.0 |
| 日本語コード生成 (API) | 10.0 | **10.0** | — |
| 日本語コード生成 (アルゴリズム) | 10.0 | **10.0** | — |
| 日本語コード生成 (DB) | 9.0 | **10.0** | +1.0 |
| 日本語デバッグ (TypeError) | 10.0 | **10.0** | — |
| 日本語デバッグ (KeyError) | 10.0 | **10.0** | — |
| 日本語コードレビュー | 8.0 | **10.0** | +2.0 |
| Git戦略提案 | 10.0 | **10.0** | — |
| 自己修正 | 10.0 | **10.0** | — |
| ドキュメント生成 | 10.0 | **10.0** | — |
| **総合** | **9.4** | **10.0** | **+0.6** |

### 改善が顕著だったポイント

**Function Calling (+2.0)**: ベースモデルは余計な説明文を付けがちですが、学習後は `<tool_call>` 形式のクリーンな JSON を即座に出力。

**Multi-step ReAct (+2.0)**: Thought → Action → Observation の構造化されたフローを JSON で出力。エージェントループとの相性が大幅に向上。

**コードレビュー (+2.0)**: SQL インジェクションの指摘だけでなく、パラメータ化クエリの具体的な修正コードまで提示。

## 学習の詳細

```
ベースモデル: google/gemma-4-31b-it
手法: QLoRA (4-bit NF4, double quantization)
LoRA: r=16, alpha=32, dropout=0.05
対象: q/k/v/o_proj, gate/up/down_proj
学習データ: 1,546 サンプル (v2)
エポック: 2 (Loss 0.98, Token Accuracy 96.8%)
学習時間: 約1.5時間
GPU: NVIDIA RTX PRO 6000 (96GB VRAM)
```

### Gemma4 特有のハマりポイント

Gemma4 のファインチューニングには 2 つの monkey-patch が必要でした。

**1. Gemma4ClippableLinear 対応**

Gemma4 は独自の `ClippableLinear` レイヤーを使っており、PEFT がサポートしていません。

```python
import peft.tuners.lora.model as lora_model
_orig = lora_model.LoraModel._create_new_module

def _patched(lora_config, adapter_name, target, **kwargs):
    try:
        return _orig(lora_config, adapter_name, target, **kwargs)
    except ValueError:
        if hasattr(target, 'linear'):
            return _orig(lora_config, adapter_name, target.linear, **kwargs)
        raise

lora_model.LoraModel._create_new_module = staticmethod(_patched)
```

**2. mm_token_type_ids の自動注入**

Gemma4 はマルチモーダルアーキテクチャのため、テキストのみの学習でも `mm_token_type_ids` が必要です。

```python
_orig_forward = model.forward
def _patched_forward(*args, **kwargs):
    if "mm_token_type_ids" not in kwargs and "input_ids" in kwargs:
        kwargs["mm_token_type_ids"] = torch.zeros_like(kwargs["input_ids"])
    return _orig_forward(*args, **kwargs)
model.forward = _patched_forward
```

## 使い方

### transformers + PEFT

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
import torch

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                          bnb_4bit_compute_dtype=torch.bfloat16)
base = AutoModelForCausalLM.from_pretrained("google/gemma-4-31b-it",
                                              quantization_config=bnb, device_map="auto")
model = PeftModel.from_pretrained(base, "Tsunamayo7/gemma4-31b-ja-agent-coder")
tokenizer = AutoTokenizer.from_pretrained("Tsunamayo7/gemma4-31b-ja-agent-coder")
```

### Claude Code のサブエージェントとして

[helix-agents](https://github.com/tsunamayo7/helix-agents) MCP サーバーを使えば、Claude Code から直接このモデルに作業を委譲できます。

```json
{
  "mcpServers": {
    "helix-agents": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/helix-agent", "python", "server.py"]
    }
  }
}
```

## なぜ Gemma4 を選んだか

- **31B パラメータ**: 20GB VRAM で 4-bit 推論可能（コンシューマ GPU で動作）
- **マルチモーダル対応**: テキスト+画像の両方に対応するアーキテクチャ
- **Apache 2.0 ライセンス**: 商用利用可、改変自由
- **日本語性能**: ベースでも日本語コーディングが十分に強い（9.4/10）

## まとめ

Gemma4-31B はベースでも日本語コーディング能力が高いですが、QLoRA ファインチューニングにより**Function Calling、ReAct 推論、コードレビュー**の品質が向上しました。特にエージェント型の構造化出力で改善が顕著です。

Claude Code のトークン消費を抑えたい方は、ぜひローカルサブエージェントとしてお試しください。

**リポジトリ**: [HuggingFace](https://huggingface.co/Tsunamayo7/gemma4-31b-ja-agent-coder) | [helix-agents](https://github.com/tsunamayo7/helix-agents)
