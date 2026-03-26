# Mixture of Experts (MoE) 完全ガイド — 2026年版：LLMの主流アーキテクチャを徹底解説

> **想定読者**: AI/MLエンジニア、LLMに関心のある開発者
> **読了時間**: 約15分

---

## はじめに

2025年から2026年にかけて、大規模言語モデル（LLM）の世界で **Mixture of Experts（MoE）** アーキテクチャが爆発的に普及しました。DeepSeek-V3、Qwen3、Mixtral、DBRX、Llama 4 Maverick — 主要なオープンソースモデルの多くがMoEを採用しています。

MoEの核心は極めてシンプルです：**「モデルのすべての部分を、すべての入力に対して常にアクティブにする必要はない」**。この考え方が、効率性とスケーラビリティの劇的な向上をもたらしました。

本記事では、MoEの基礎原理から最新モデルの実装詳細、推論デプロイの課題まで、技術的に深掘りしていきます。

---

## 1. MoEとは何か

### 1.1 基本概念

Mixture of Experts は、複数の「エキスパート」ネットワークと、入力に応じてどのエキスパートを使うかを決定する「ゲーティングネットワーク（ルーター）」で構成されるアーキテクチャです。

```
入力トークン
    │
    ▼
┌──────────┐
│  Router   │  ← どのExpertに送るか決定
│ (Gating)  │
└──────────┘
    │
    ├──► Expert 1  ✓ (選択)
    ├──► Expert 2  ✗
    ├──► Expert 3  ✓ (選択)
    ├──► Expert 4  ✗
    │    ...
    └──► Expert N  ✗
    │
    ▼
重み付き合成 → 出力
```

Transformerモデルの文脈では、通常のFeed-Forward Network（FFN）レイヤーをMoEレイヤーに置き換えます。各MoEレイヤーには複数のエキスパート（それぞれがFFN）が存在し、ルーターが各トークンをどのエキスパートに送るかを動的に決定します。

### 1.2 Dense vs Sparse: 何が違うのか

| 特性 | Dense モデル | Sparse MoE モデル |
|------|------------|------------------|
| **パラメータ活性化** | 全パラメータが毎回活性化 | 一部のExpertのみ活性化 |
| **計算コスト** | パラメータ数に比例 | アクティブパラメータ数に比例 |
| **メモリ使用量** | パラメータ数に比例 | 全パラメータをメモリに保持が必要 |
| **スケーラビリティ** | 計算コスト増大が壁 | パラメータ追加が比較的容易 |

**重要なポイント**: MoEモデルは「総パラメータ数」と「アクティブパラメータ数」が大きく異なります。例えばDeepSeek-V3は総パラメータ671Bですが、各トークンの処理に活性化されるのは37Bのみです。

---

## 2. ルーティング機構の深掘り

MoEモデルの性能を左右する最も重要なコンポーネントがルーター（ゲーティングネットワーク）です。

### 2.1 Top-K ゲーティング

最も基本的なルーティング手法です。

- **Top-1 ゲーティング**: 各トークンを最もスコアの高い1つのエキスパートにのみ送る。Switch Transformerが採用。最も計算効率が高いが、表現力が限られる。
- **Top-2 ゲーティング**: 各トークンを上位2つのエキスパートに送り、出力を重み付きで合成する。Mixtralが採用。計算コストと表現力のバランスが良い。

```python
# Top-K ゲーティングの概念的な実装
def top_k_gating(token_embedding, expert_weights, k=2):
    # ルーターのスコア計算
    logits = token_embedding @ expert_weights  # [num_experts]

    # 上位K個のExpertを選択
    top_k_values, top_k_indices = torch.topk(logits, k)

    # Softmaxで重みを正規化
    weights = F.softmax(top_k_values, dim=-1)

    return top_k_indices, weights
```

### 2.2 Noisy Top-K ゲーティング

Shazeer et al. (2017) の「Sparsely-Gated Mixture-of-Experts Layer」で導入された手法。ゲーティングの前に標準正規分布のノイズを加えることで、学習時のエキスパート利用の偏りを軽減します。

```
G(x) = Softmax(TopK(H(x) + StandardNormal() · Softplus(W_noise · x)))
```

### 2.3 Expert Choice ルーティング

従来の「トークンがエキスパートを選ぶ」方式を逆転させた手法。**エキスパートが処理するトークンを選ぶ**ことで、完全な負荷分散を保証します。

- 各エキスパートが固定数のトークンを受け取る
- トークンごとのエキスパート数が可変になる
- 学習効率の大幅な向上が報告されている

### 2.4 負荷分散の課題

ルーティングにおける最大の課題は **負荷分散（Load Balancing）** です。

ナイーブなルーティングでは、一部のエキスパートにトークンが集中し（routing collapse）、他のエキスパートが遊休状態になります。これは計算効率を著しく低下させます。

**従来のアプローチ**: 補助損失関数（auxiliary loss）を追加し、エキスパートの利用率を均等にする方向に学習を促す。ただし、補助損失が大きすぎるとモデル性能が低下するトレードオフがある。

**最新のアプローチ**:
- **Skywork-MoE**: ゲーティングロジットの正規化と適応的な補助損失係数で、レイヤーごとに最適なバランスを自動調整
- **JetMoE**: トークンドロップを排除し、ブロックスパース行列演算でGPUカーネルレベルの最適化を実現

---

## 3. 主要MoEモデルの比較（2024-2026）

### 3.1 モデル一覧

| モデル | 総パラメータ | アクティブ | Expert数 | アクティブExpert | 特徴 |
|--------|-----------|-----------|----------|-----------------|------|
| **Mixtral 8x7B** | 46.7B | 12.9B | 8 | 2 | MoE普及の先駆け |
| **DBRX** | 132B | 36B | 16 | 4 | Fine-grained MoE |
| **DeepSeek-V3** | 671B | 37B | 256+1 | 8+1 | Auxiliary-loss-free |
| **Qwen3 235B** | 235B | 22B | — | — | DeepSeekに近い設計 |
| **Llama 4 Maverick** | — | — | — | 2 | Dense/MoE交互配置 |
| **Qwen3.5 397B** | 397B | 17B | — | — | マルチモーダル対応 |

### 3.2 DeepSeek-V3: MoE設計の最前線

DeepSeek-V3は2024年末に発表され、MoEアーキテクチャの革新を多数導入しました。

#### Auxiliary-Loss-Free 負荷分散

従来のMoEモデルが補助損失関数に頼っていた負荷分散を、**補助損失なし**で実現した画期的な手法です。

- 補助損失のトレードオフ（バランス vs 性能）を解消
- 学習全体を通じて良好な負荷分散を維持
- **トークンドロップなし**で学習を完遂

#### Multi-head Latent Attention (MLA)

KVキャッシュを低ランク潜在空間に圧縮することで、推論時のメモリ消費を大幅に削減。MoEとは独立した技術ですが、MoEの大規模パラメータとの組み合わせで特に効果を発揮します。

#### DeepSeekMoE の構成

- **256個のルーテッドエキスパート** + **1個の共有エキスパート**
- 各トークンは8個のルーテッドエキスパート + 共有エキスパートで処理
- 最初の3層を除く全Transformerブロックでこの構成を使用
- Multi-Token Prediction (MTP) による投機的デコード対応

### 3.3 Fine-grained MoE: DBRXのアプローチ

DBRXは「細粒度MoE」を採用し、**多数の小さなエキスパート**を使用します。16個のエキスパートから4個を選択する構成で、少数の大きなエキスパートを使う従来手法と比較して、より柔軟な知識の組み合わせが可能になります。Grok-1（2倍以上のサイズ）やCodeLLaMA-70Bを上回るコーディング性能を達成しています。

### 3.4 アーキテクチャの多様化

**Llama 4 Maverick** は、MoEレイヤーとDenseレイヤーを**交互に配置**する独自のハイブリッドアプローチを採用。全層をMoEにするDeepSeekとは対照的な設計思想です。各エキスパートの隠れ層サイズは8,192と大きく（DeepSeekは2,048）、少数の大型エキスパートを選択する方式です。

**Qwen3** シリーズは、初期のQwen-MoEでは共有エキスパートを使用していましたが、Qwen3 235Bでは共有エキスパートを廃止。さらにQwen3-Coder-Next（80B/3Bアクティブ）はDeepSeek-V3.2（37Bアクティブ）をコーディングタスクで上回るなど、パラメータ効率の高さを示しています。

---

## 4. 推論とデプロイの課題

MoEモデルの実運用には、Dense モデルとは異なる独自の課題があります。

### 4.1 メモリの壁

MoEの最大の矛盾：**計算はスパースだが、メモリはデンス**。

各トークンの処理には一部のエキスパートしか使いませんが、全エキスパートのパラメータを高帯域メモリに保持する必要があります。DeepSeek-V3（671B）の場合、全パラメータのロードには**13,719 GB/s**のメモリ帯域幅が必要とされます。

```
Dense 70B モデル:  70B パラメータ → ~140GB (FP16)
MoE 671B モデル: 671B パラメータ → ~1,342GB (FP16)
                  ※ 実際の計算量は37B相当だが、メモリは全パラメータ分必要
```

### 4.2 Expert Parallelism（EP）

大規模MoEモデルの推論では、エキスパートを複数のGPUに分散配置する **Expert Parallelism** が不可欠です。

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│  GPU 0  │  │  GPU 1  │  │  GPU 2  │  │  GPU 3  │
│Expert0-3│  │Expert4-7│  │Expert8-B│  │ExpertC-F│
└────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘
     │            │            │            │
     └────────── All-to-All 通信 ──────────┘
```

**課題**: All-to-All通信がエンドツーエンドレイテンシの**10-30%**を占める場合があります。

#### NVIDIA Wide Expert Parallelism

NVIDIAのGB200 NVL72向けWide-EPは、130 TB/sのNVLinkコヒーレントドメインを活用し、従来比で最大**1.8倍**のGPUあたりスループットを実現します。

### 4.3 CPU/GPUハイブリッド推論

メモリ制約の緩和策として、**KTransformers** などのフレームワークがCPU/GPUハイブリッド推論を実現しています。

- アクティブなエキスパートのみGPUに配置
- 非アクティブなエキスパートはCPUメモリ（DRAM）にオフロード
- 帯域幅がボトルネックだが、コンシューマGPUでも大規模MoE推論が可能に

### 4.4 推論時の負荷不均衡

学習時には補助損失で負荷分散を促しますが、推論時にはこの損失が適用されません。そのため、特定のプロンプトやタスクによっては、エキスパートへのトークン分配が大きく偏る可能性があります。これがExpert Parallelism環境でのGPU利用効率低下の一因となります。

---

## 5. MoEのメリットとデメリット

### メリット

1. **学習効率**: 同じ計算予算で、Dense モデルよりはるかに大きなモデルを学習可能
2. **推論速度**: アクティブパラメータが少ないため、同等性能のDenseモデルより高速
3. **スケーラビリティ**: エキスパートの追加でモデル容量を効率的に拡張可能
4. **専門化**: 各エキスパートが異なるタスクやドメインに特化しうる

### デメリット

1. **メモリフットプリント**: 全パラメータをメモリに保持する必要がある
2. **通信オーバーヘッド**: 分散推論時のAll-to-All通信がボトルネック
3. **学習の不安定性**: ルーティングの崩壊（routing collapse）のリスク
4. **ファインチューニングの困難さ**: エキスパートの専門性を維持しつつ調整が難しい
5. **負荷分散**: 実用的な負荷分散の実現が技術的に困難

---

## 6. MoEの歴史と今後の展望

### 歴史的経緯

| 年 | マイルストーン |
|----|------------|
| 1991 | Jacobs et al. がMixture of Expertsの概念を提案 |
| 2017 | Shazeer et al. Sparsely-Gated MoE Layer（Google） |
| 2022 | Switch Transformer — Top-1ルーティングで効率化 |
| 2022 | Expert Choice Routing — エキスパート側からの選択 |
| 2023 | Mixtral 8x7B — オープンソースMoEの普及 |
| 2024 | DeepSeek-V3 — Auxiliary-loss-free, 256エキスパート |
| 2024 | DBRX — Fine-grained MoE |
| 2025 | Qwen3, Llama 4 — MoEが主流アーキテクチャに |
| 2026 | Qwen3.5-397B, DeepSeek-V3.2 — さらなる大規模化と効率化 |

### 今後のトレンド

1. **ルーティング手法の進化**: 学習可能で負荷分散を自然に達成するルーター設計
2. **ハードウェア最適化**: MoE専用のアクセラレータやネットワーク設計
3. **マルチモーダルMoE**: テキスト、画像、音声を専門エキスパートで処理
4. **動的エキスパート数**: 入力の複雑さに応じてアクティブエキスパート数を変動
5. **エッジデプロイ**: CPU/GPUハイブリッド推論の発展でローカル実行が現実的に

---

## まとめ

Mixture of Experts は、「必要なパラメータだけを使う」というシンプルな原理から、LLMのスケーラビリティと効率性を劇的に改善するアーキテクチャです。

2026年現在、MoEは実験的な手法から**LLMの主流アーキテクチャ**へと進化しました。DeepSeek-V3のAuxiliary-loss-free負荷分散、Expert Choice Routingなどの技術革新により、かつての課題が次々と克服されています。

一方で、メモリフットプリントの大きさや推論時の通信オーバーヘッドなど、実運用上の課題も依然として存在します。これらの課題は、ハードウェアの進化（NVLink、HBM4）とソフトウェア最適化（KTransformers、Wide-EP）の両面からアプローチされており、今後数年でさらなるブレークスルーが期待されます。

MoEを理解することは、現代のLLMを理解する上で不可欠です。本記事が、その第一歩となれば幸いです。

---

## 参考文献

- [Mixture of Experts Explained — Hugging Face Blog](https://huggingface.co/blog/moe)
- [A Visual Guide to Mixture of Experts — Maarten Grootendorst](https://newsletter.maartengrootendorst.com/p/a-visual-guide-to-mixture-of-experts)
- [DeepSeek-V3 Technical Report — arXiv](https://arxiv.org/abs/2412.19437)
- [The Rise of MoE: Comparing 2025's Leading MoE Models — Friendli AI](https://friendli.ai/blog/moe-models-comparison)
- [Applying Mixture of Experts in LLM Architectures — NVIDIA Technical Blog](https://developer.nvidia.com/blog/applying-mixture-of-experts-in-llm-architectures/)
- [Router Wars: Which MoE Routing Strategy Actually Works — Cerebras](https://www.cerebras.ai/blog/moe-guide-router)
- [A Review on the Evolvement of Load Balancing Strategy in MoE LLMs — Hugging Face](https://huggingface.co/blog/NormalUhr/moe-balance)
- [Scaling Large MoE Models with Wide Expert Parallelism — NVIDIA](https://developer.nvidia.com/blog/scaling-large-moe-models-with-wide-expert-parallelism-on-nvl72-rack-scale-systems/)
- [MoE-Lightning: High-Throughput MoE Inference — ASPLOS 2025](https://pschafhalter.com/papers/2025-asplos-moe-lightning.pdf)
- [A Technical Tour of the DeepSeek Models — Sebastian Raschka](https://magazine.sebastianraschka.com/p/technical-deepseek)
- [Mixture-of-Experts with Expert Choice Routing — arXiv](https://arxiv.org/pdf/2202.09368)
- [A Comprehensive Survey of Mixture-of-Experts — arXiv](https://arxiv.org/html/2503.07137v1)
