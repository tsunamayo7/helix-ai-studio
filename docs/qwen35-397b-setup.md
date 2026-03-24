# Qwen3.5-397B-A17B ローカル導入手順

96GB VRAM環境でQwen3.5-397B-A17B（MoEモデル）をllama.cppで動かす手順です。

## モデル概要

| 項目 | 値 |
|------|-----|
| 総パラメータ | 397B |
| 推論時アクティブ | 17B（MoE） |
| 推奨量子化 | IQ2_XS (~130GB) or Q2_K (~160GB) |
| 接続方式 | llama-server → OpenAI互換API → Helix AI Studio |

## 必要環境

- GPU: 96GB+ VRAM（RTX PRO 6000等）
- RAM: 64GB+
- ストレージ: 200GB+ 空き容量
- llama.cpp（最新版）

## Step 1: llama.cppのインストール

```bash
# Windows（CMake + CUDA）
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j

# または prebuilt バイナリをダウンロード
# https://github.com/ggml-org/llama.cpp/releases
```

## Step 2: モデルのダウンロード

```bash
# HuggingFace からGGUFをダウンロード
# 推奨: IQ2_XS（~130GB、96GB GPU + RAM分割で動作）

# huggingface-cli を使う場合
pip install huggingface-hub
huggingface-cli download unsloth/Qwen3.5-397B-A17B-GGUF \
  --include "Qwen3.5-397B-A17B-UD-IQ2_XS*.gguf" \
  --local-dir ./models/qwen35-397b

# Q2_Kの場合（~160GB、より高品質だがRAM使用量多い）
# huggingface-cli download unsloth/Qwen3.5-397B-A17B-GGUF \
#   --include "Qwen3.5-397B-A17B-Q2_K*.gguf" \
#   --local-dir ./models/qwen35-397b
```

## Step 3: llama-server起動（MoE Expert CPU Offload）

```bash
# MoE Expert層をCPUにオフロードし、常時アクティブ層をGPUに配置
./build/bin/llama-server \
  -m ./models/qwen35-397b/Qwen3.5-397B-A17B-UD-IQ2_XS.gguf \
  --host 0.0.0.0 \
  --port 8090 \
  -ngl 999 \
  -ot ".ffn_.*_exps.=CPU" \
  --ctx-size 8192 \
  --threads 16

# オプション説明:
#   -ngl 999        : 可能な限りGPUにレイヤーをオフロード
#   -ot "...=CPU"   : MoE Expert FFN層をCPUに配置（VRAMに載らない部分）
#   --ctx-size 8192 : コンテキスト長（VRAM節約のため控えめに）
#   --threads 16    : CPUスレッド数（Core Ultra 7に合わせて調整）
```

### Windows PowerShell版

```powershell
.\build\bin\Release\llama-server.exe `
  -m .\models\qwen35-397b\Qwen3.5-397B-A17B-UD-IQ2_XS.gguf `
  --host 0.0.0.0 `
  --port 8090 `
  -ngl 999 `
  -ot ".ffn_.*_exps.=CPU" `
  --ctx-size 8192 `
  --threads 16
```

## Step 4: Helix AI Studioで接続

1. ブラウザで http://localhost:8502/settings を開く
2. 「ローカルAI設定」セクション
3. **OpenAI互換API URL** に `http://localhost:8090/v1` を入力
4. **保存** をクリック

チャット画面で「ローカル」→「OpenAI互換」を選択すると、Qwen3.5-397Bが表示されます。

## Step 5: 自動起動設定（オプション）

```bat
@echo off
title Qwen3.5-397B Server
cd /d "C:\path\to\llama.cpp"
build\bin\Release\llama-server.exe ^
  -m models\qwen35-397b\Qwen3.5-397B-A17B-UD-IQ2_XS.gguf ^
  --host 0.0.0.0 --port 8090 ^
  -ngl 999 -ot ".ffn_.*_exps.=CPU" ^
  --ctx-size 8192 --threads 16
pause
```

## VRAM使用量の目安

```
IQ2_XS (~130GB):
  GPU (96GB): 常時アクティブ層 + 一部Expert → ~85GB使用
  RAM (64GB): 残りのExpert層 → ~45GB使用
  推論速度: 5-10 tok/s

Q2_K (~160GB):
  GPU (96GB): 常時アクティブ層 + 一部Expert → ~90GB使用
  RAM (64GB): 残りのExpert層 → ~70GB使用 ← ギリギリ
  推論速度: 3-5 tok/s
```

## 注意事項

- llama-server起動中はOllamaの大型モデル（120B等）と同時使用不可（VRAM競合）
- Ollamaの小型モデル（8B以下）なら同時使用可能
- コンテキスト長を増やすとVRAM使用量が増加（8192推奨）
- 初回起動時のモデルロードに数分かかる

## トラブルシューティング

| 症状 | 対策 |
|------|------|
| CUDA out of memory | `--ctx-size` を4096に下げる、または `-ot` でより多くの層をCPUに |
| 速度が極端に遅い | Ollamaの大型モデルをunloadする: `ollama stop <model>` |
| サーバーが起動しない | llama.cppをCUDA有効でリビルド |
| モデルが見つからない | GGUFファイルパスを確認、分割ファイルの場合は全パーツをダウンロード |
