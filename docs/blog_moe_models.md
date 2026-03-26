# Mixture of Experts（MoE）完全ガイド：スパース活性化が切り拓くLLMの未来

> **概要**: 2025〜2026年、LLMの主流アーキテクチャは「Dense（密）モデル」から「MoE（Mixture of Experts：混合専門家）モデル」へと急速にシフトしています。GPT-5、DeepSeek-V3、Qwen3、Llama 4——最前線のモデルはすべてMoEを採用しています。本記事では、MoEの基本原理から最新モデルの比較、実運用上の課題まで、技術者向けに徹底解説します。

---

## 目次

1. [MoEとは何か？](#1-moeとは何か)
2. [アーキテクチャの詳細](#2-アーキテクチャの詳細)
3. [なぜMoEが主流になったのか](#3-なぜmoeが主流になったのか)
4. [主要MoEモデル比較（2025-2026）](#4-主要moeモデル比較2025-2026)
5. [DeepSeek-V3の技術革新](#5-deepseek-v3の技術革新)
6. [MoEの課題と対策](#6-moeの課題と対策)
7. [今後の展望](#7-今後の展望)
8. [まとめ](#8-まとめ)

---

## 1. MoEとは何か？

### 基本コンセプト

Mixture of Experts（MoE）は、**複数の「専門家（Expert）」ネットワークと、入力に応じて適切な専門家を選択する「ルーター（Router/Gate）」** を組み合わせたアーキテクチャです。

通常のDenseモデルでは、すべてのパラメータが毎回の推論で活性化されます。一方MoEでは、**入力トークンごとに一部の専門家のみが活性化**される「スパース活性化（Sparse Activation）」により、総パラメータ数を大幅に増やしながらも、推論時の計算量を抑えることができます。

```
┌─────────────────────────────────────────────┐
│              入力トークン                      │
│                  ↓                            │
│         ┌───────────────┐                    │
│         │   ルーター     │                    │
│         │  (Gate Network)│                    │
│         └───┬───┬───┬───┘                    │
│             │   │   │                        │
│      ┌──────┘   │   └──────┐                 │
│      ↓          ↓          ↓                 │
│  ┌────────┐ ┌────────┐ ┌────────┐            │
│  │Expert 1│ │Expert 2│ │Expert 3│ ... Expert N│
│  │(活性化) │ │(休止)  │ │(活性化) │            │
│  └────┬───┘ └────────┘ └────┬───┘            │
│       │                     │                │
│       └─────────┬───────────┘                │
│                 ↓                            │
│          重み付き合成                          │
│                 ↓                            │
│              出力                             │
└─────────────────────────────────────────────┘
```

### 具体例で理解する

たとえば、DeepSeek-V3は**総パラメータ671B**のモデルですが、各トークンの推論で活性化されるのは**わずか37B**です。つまり、671Bの知識を持ちながら、37Bモデル程度の計算コストで動作します。これがMoEの最大の魅力です。

---

## 2. アーキテクチャの詳細

### 2.1 Transformerへの統合

MoEはTransformerアーキテクチャの**FFN（Feed-Forward Network）層を置き換える**形で統合されます。Self-Attention層はそのまま維持され、FFN層が複数のExpertに分割されます。

```
通常のTransformerブロック        MoE Transformerブロック
┌──────────────────┐          ┌──────────────────┐
│  Self-Attention   │          │  Self-Attention   │
├──────────────────┤          ├──────────────────┤
│      FFN          │    →     │  Router + Experts │
│  (全パラメータ活性)│          │  (スパース活性化)  │
└──────────────────┘          └──────────────────┘
```

### 2.2 ルーティング戦略

ルーターは入力ベクトル `x` にルーター重み行列 `W` を掛け、Softmaxで確率分布に変換し、上位K個の専門家を選択します。

#### Top-K ルーティング

最も一般的な方式です。各トークンに対してK個の専門家を選択し、その出力を重み付き平均で合成します。

- **Top-1**: 各トークンを1つの専門家にのみ送る（Switch Transformer方式）
- **Top-2**: 2つの専門家の出力を重み付き合成（Mixtral方式）
- **Top-8+**: より多くの専門家を活用（Qwen3は8つ、DeepSeek-V3は8+1共有）

```python
# ルーティングの擬似コード
def moe_forward(x, router, experts, k=2):
    # ルーターで各専門家のスコアを計算
    scores = softmax(router(x))  # [num_experts]

    # Top-K専門家を選択
    top_k_indices = topk(scores, k)
    top_k_weights = scores[top_k_indices]

    # 選択された専門家の出力を重み付き合成
    output = sum(w * experts[i](x) for i, w in zip(top_k_indices, top_k_weights))
    return output
```

#### Expert Choice ルーティング

Top-Kではトークンが専門家を選びますが、**Expert Choiceでは専門家がトークンを選ぶ**逆の方式です。各専門家が処理したいトークンを選ぶため、負荷分散が自然に実現されます。

#### 共有Expert（Shared Expert）

DeepSeek-V3やLlama 4が採用する方式で、**常に活性化される「共有Expert」と、ルーティングされる「専門Expert」** を組み合わせます。共有Expertが汎用的な知識を担当し、専門Expertが特化タスクを処理します。

```
入力 → ルーター → [Expert A, Expert B]（Top-K選択）
  │
  └──→ [Shared Expert]（常時活性化）

出力 = Shared Expert(x) + Σ(weight_i × Expert_i(x))
```

### 2.3 負荷分散（Load Balancing）

MoEの最大の訓練課題は**負荷の不均衡**です。特定の専門家にトークンが集中し、他の専門家が「死んだ」状態になる問題です。

#### 補助損失（Auxiliary Loss）

従来の標準的な手法で、各専門家への負荷が均等になるよう追加の損失関数を設けます。

```
L_aux = α × N × Σ(f_i × P_i)

f_i: Expert iに割り当てられたトークンの割合
P_i: Expert iのルーター確率の平均
α: バランス係数
```

**問題点**: 補助損失の強度調整が難しく、強すぎるとモデル性能が低下し、弱すぎると負荷分散が効かない。

#### ノイズ注入（KeepTopK with Noise）

ルーティングスコアに学習可能なガウシアンノイズを加えることで、常に同じ専門家が選ばれることを防ぎます。

#### Auxiliary-Loss-Free（DeepSeek-V3方式）

DeepSeek-V3が提案した画期的な方法です。補助損失を使わず、**各専門家にバイアス項を動的に付与**し、過負荷/低負荷の専門家のバイアスを訓練ステップごとに調整します。性能低下なしに負荷分散を実現できる革新的な手法です。

### 2.4 Expert容量とトークンドロップ

各専門家が処理できるトークン数には上限（Expert Capacity）があります。

```
Capacity = (batch_size × seq_len × capacity_factor) / num_experts
```

容量を超えたトークンは**ドロップ（スキップ）** され、次の層にそのまま渡されます。`capacity_factor` の調整が推論品質に直結します。

---

## 3. なぜMoEが主流になったのか

### 3.1 スケーリング則の壁

Denseモデルのスケーリング（パラメータ数を増やす）は、FLOPs（計算量）が線形に増加します。100Bモデルは50Bモデルの約2倍の計算コストが必要です。

MoEはこの制約を打ち破ります：

| 観点 | Dense 70B | MoE 671B (37B active) |
|------|-----------|----------------------|
| 総パラメータ | 70B | 671B |
| 推論時の活性パラメータ | 70B | 37B |
| 推論FLOPs | 高い | **低い**（約半分） |
| 知識容量 | 70B分 | **671B分** |

### 3.2 訓練効率の圧倒的優位

同じ計算予算で比較した場合、MoEモデルはDenseモデルを明確に上回ります。Mixtral 8x7B（活性パラメータ12.8B）はLlama 2 70Bに匹敵する性能を、はるかに少ない計算量で達成しました。

### 3.3 推論コストの削減

大規模サービスでは推論コストが支配的です。MoEは少ない活性パラメータで高品質な出力を得られるため、**APIサービスのコスト効率**が大幅に向上します。

---

## 4. 主要MoEモデル比較（2025-2026）

### モデルスペック一覧

| モデル | 総パラメータ | 活性パラメータ | Expert数 | 活性Expert | コンテキスト長 |
|--------|------------|-------------|---------|-----------|------------|
| **GPT-OSS 120B** | 117B | 5.1B | 128 | 4 | 128K |
| **GPT-OSS 20B** | 21B | 3.6B | 32 | 4 | 128K |
| **DeepSeek-R1-0528** | 671B | 37B | 256 | 8+1共有 | 128K |
| **Llama 4 Maverick** | 400B | 17B | 128 | 1+1共有 | 1M |
| **Llama 4 Scout** | 109B | 17B | 16 | 1+1共有 | 10M |
| **Qwen3-235B** | 235B | 22B | 128 | 8 | 32K (YaRN 131K) |
| **Qwen3-30B** | 30.5B | 3.3B | 128 | 8 | 32K (YaRN 131K) |
| **Mixtral 8x22B** | 141B | 39B | 8 | 2 | 64K |
| **DBRX** | 132B | 36B | 16 | 4 | 32K |

### ルーティング設計の違い

MoEモデルは大きく2つの設計思想に分かれます：

**共有Expert あり（DeepSeek, Llama 4）**
- 常時活性化の共有Expertが汎化能力を担保
- 専門Expertは特化タスクに集中
- 安定性が高く、汎用タスクに強い

**共有Expert なし（GPT-OSS, Qwen3）**
- すべてのExpertがルーティングで選択
- よりシンプルな設計
- Expert数が多い場合に効率的

### 注目の性能ハイライト

**Qwen3-Coder-Next (80B / 3B active)**
2026年2月発表。活性パラメータわずか3Bでありながら、DeepSeek V3.2（37B active）やKimi K2.5（32B active）をコーディングタスクで上回り、Claude Sonnet 4.5に迫る性能を達成。MoEの効率性を極限まで追求した成果です。

**Llama 4 Maverick / Scout**
100万〜1000万トークンの超長コンテキストをサポート。マルチモーダル（画像+テキスト）対応で、MoEの応用範囲を拡張しています。

**DeepSeek-R1-0528**
256個という大規模なExpertプールと、Auxiliary-Loss-Free負荷分散を組み合わせ、推論（Reasoning）タスクで最高水準の性能を実現しています。

---

## 5. DeepSeek-V3の技術革新

DeepSeek-V3は2024年末に発表され、MoEアーキテクチャに複数の革新をもたらしました。ここでは主要な技術的ブレークスルーを解説します。

### 5.1 Auxiliary-Loss-Free Load Balancing

従来の補助損失による負荷分散は「性能とバランスのトレードオフ」がありました。DeepSeek-V3は**バイアス項の動的調整**でこれを解決します。

```
routing_score = softmax(W × x + bias)

各訓練ステップで:
  if Expert_i が過負荷 → bias_i -= γ
  if Expert_i が低負荷 → bias_i += γ
```

この方法の利点：
- 勾配に影響を与えないため、モデル性能を損なわない
- シンプルなヒューリスティックで安定した負荷分散を実現
- 追加のハイパーパラメータ調整がほぼ不要

### 5.2 Multi-Head Latent Attention（MLA）

MoEとは直接関係しませんが、DeepSeek-V3の推論効率を支える重要な技術です。

通常のMulti-Head Attentionでは、KeyとValueのキャッシュ（KVキャッシュ）が長文コンテキストで膨大なメモリを消費します。MLAは**KeyとValueを低次元の潜在空間に圧縮**し、KVキャッシュサイズを大幅に削減します。

```
標準MHA:   KVキャッシュ = 2 × num_heads × head_dim × seq_len
MLA:       KVキャッシュ = 2 × latent_dim × seq_len  (latent_dim << num_heads × head_dim)
```

### 5.3 Multi-Token Prediction（MTP）

訓練時に次の1トークンだけでなく**複数トークンを同時に予測**する手法です。表現学習の効率が向上し、最終的なモデル性能が改善されます。また、推論時にはspeculative decoding（投機的復号）と組み合わせてスループットを向上させることも可能です。

---

## 6. MoEの課題と対策

### 6.1 メモリ使用量

MoEモデルは活性パラメータ数に比べて**総パラメータ数が大きい**ため、すべてのExpertをメモリに載せる必要があります。

| 課題 | 詳細 |
|------|------|
| VRAM要件 | DeepSeek-V3 (671B) はFP16で約1.3TBのVRAMが必要 |
| Expert並列 | 複数GPUにExpertを分散配置する必要がある |

**対策**:
- **量子化**: FP4/INT4量子化で必要VRAM を1/4に削減（DeepSeek-V3のFP4版は約160GBで動作）
- **Expert並列（EP）**: Expert群を複数GPUに分散
- **Expert Offloading**: 使用頻度の低いExpertをCPUメモリやSSDに退避

### 6.2 通信オーバーヘッド

分散推論時、トークンを適切なExpertに送る**All-to-All通信**がボトルネックになります。

**対策**:
- **Expert並列 + テンソル並列**の組み合わせ
- **Expert配置の最適化**: 共起頻度の高いExpertを同一ノードに配置
- **通信と計算のオーバーラップ**: パイプライニングで通信遅延を隠蔽

### 6.3 Expert崩壊（Expert Collapse）

訓練中に一部のExpertにトークンが集中し、他のExpertが学習しなくなる現象です。

**対策**:
- Auxiliary-Loss-Free Load Balancing（DeepSeek方式）
- ノイズ注入によるExploration促進
- Expert Capacity制限によるトークンドロップ

### 6.4 Fine-tuningの難しさ

MoEモデルのFine-tuningでは、ルーティングパターンが崩れやすい問題があります。

**対策**:
- **LoRA + Router凍結**: Expertの重みのみをLoRAで調整し、ルーターは固定
- **少数Expertのみ更新**: タスクに関連するExpertだけをFine-tuning
- **Expert Merging**: Fine-tuning後に類似Expertを統合してモデルサイズを削減

---

## 7. 今後の展望

### 7.1 MoEの進化方向

1. **Expert数の大規模化**: 256 → 1000+のExpertプールで、より細かい専門分化
2. **マルチモーダルMoE**: テキスト/画像/音声それぞれに特化したExpert群（Llama 4が先駆）
3. **動的Expert追加**: 新タスクに合わせてExpertを後から追加できるアーキテクチャ
4. **ハードウェア最適化**: MoE専用のチップ設計やネットワークトポロジー

### 7.2 Denseモデルとの棲み分け

MoEがすべてのユースケースでDenseを置き換えるわけではありません：

| 用途 | 推奨アーキテクチャ |
|------|------------------|
| 大規模APIサービス | **MoE**（コスト効率が高い） |
| エッジデバイス | **Dense**（メモリ制約が厳しい） |
| 特化型タスク | **Dense**（シンプルで安定） |
| 汎用推論/コーディング | **MoE**（知識容量が大きい） |

### 7.3 オープンソースの加速

2025年以降、MoEのオープンソース化が急速に進んでいます。OLMoE（完全オープン）、DeepSeek-V3（重み公開）、Qwen3（Apache 2.0）など、研究者・開発者がMoEを手軽に試せる環境が整ってきています。

---

## 8. まとめ

Mixture of Experts（MoE）は、**「大きなモデルの知識」と「小さなモデルの推論コスト」を両立させる**画期的なアーキテクチャです。

**要点を3行で**:
- MoEは複数のExpertからルーターが最適な少数を選ぶ「スパース活性化」方式
- 2025-2026年の最前線モデル（DeepSeek, Qwen3, Llama 4, GPT-OSS）はすべてMoE採用
- 課題（メモリ、通信、負荷分散）にも革新的な解決策が次々と登場している

AI/LLMの世界で次の大きな波は、MoEアーキテクチャのさらなる進化と民主化です。大規模言語モデルの開発に携わる方は、MoEの仕組みと最新動向を押さえておくことが不可欠でしょう。

---

## 参考資料

- [Mixture of Experts Explained - Hugging Face Blog](https://huggingface.co/blog/moe)
- [A Visual Guide to Mixture of Experts - Maarten Grootendorst](https://newsletter.maartengrootendorst.com/p/a-visual-guide-to-mixture-of-experts)
- [The Rise of MoE: Comparing 2025's Leading MoE Models - FriendliAI](https://friendli.ai/blog/moe-models-comparison)
- [DeepSeek-V3 Technical Report](https://arxiv.org/html/2412.19437v1)
- [Auxiliary-Loss-Free Load Balancing Strategy for MoE](https://arxiv.org/html/2408.15664v1)
- [A Comprehensive Survey of Mixture-of-Experts (2025)](https://arxiv.org/html/2503.07137v1)
- [Applying MoE in LLM Architectures - NVIDIA Technical Blog](https://developer.nvidia.com/blog/applying-mixture-of-experts-in-llm-architectures/)
- [Stanford CS336: スパース活性化の革命](https://automation.jp/research-report/2025-04-25-stanford-cs336-language-modeling-from-scratch-a-revolution-in-sparse-activation-efficient-extension-of-language-models-by-mixture-of-experts)
- [MoE-LLMs - Cameron R. Wolfe](https://cameronrwolfe.substack.com/p/moe-llms)
- [The Big LLM Architecture Comparison - Sebastian Raschka](https://magazine.sebastianraschka.com/p/the-big-llm-architecture-comparison)
