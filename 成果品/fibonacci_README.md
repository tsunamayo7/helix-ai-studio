# フィボナッチ数列の実装

## 概要

Pythonでのフィボナッチ数列の3つの最適化実装を提供します。用途に応じて最適な手法を選択できます。

## 実装の比較

| 実装 | 時間計算量 | 空間計算量 | 推奨用途 |
|------|-----------|-----------|----------|
| **イテレーティブ版** | O(n) | O(1) | **汎用（推奨）** |
| メモ化版（@lru_cache） | O(n) | O(n) | n < 1000（学習用） |
| 行列累乗版 | O(log n) | O(log n) | n > 10^6（超高速） |

## 使い方

### 基本的な使用

```python
from fibonacci import fibonacci

# デフォルト実装（イテレーティブ版）
result = fibonacci(100)
print(result)  # 354224848179261915075
```

### 実装を選択する場合

```python
from fibonacci import fibonacci_iterative, fibonacci_memoized, fibonacci_matrix

# イテレーティブ版: 最もシンプルで推奨
result1 = fibonacci_iterative(1000)

# メモ化版: 再帰的アプローチ（n < 1000推奨）
result2 = fibonacci_memoized(500)

# 行列累乗版: 超大きなnでも高速
result3 = fibonacci_matrix(100000)
```

## 性能ベンチマーク

実測例（環境: Python 3.12, Windows 11）:

```
[n=500]
  イテレーティブ版: 0.000ms
  メモ化版:         0.501ms
  行列累乗版:       0.000ms

[n=10000]
  イテレーティブ版: 0.998ms
  行列累乗版:       0.000ms (O(log n)の威力)
```

## テスト

全実装の正確性を検証するテストスイートを含みます:

```bash
# pytest で完全なテストスイート実行
python -m pytest test_fibonacci.py -v

# pytestなしでも基本テスト実行可能
python test_fibonacci.py
```

**テスト結果**: 83個のテスト全て合格 ✓

## 推奨実装の選び方

### イテレーティブ版（推奨）

```python
fibonacci_iterative(n)
```

**理由**:
- O(1)空間で最小限のメモリ使用
- スタックオーバーフローのリスクなし
- コードが5行程度で保守しやすい
- n = 0 ~ 10^6 まで実用的

### 行列累乗版（超高速）

```python
fibonacci_matrix(n)
```

**用途**: n > 10^6 の場合
- O(log n)の時間計算量
- 10万番目のフィボナッチ数も1秒以内

### メモ化版（学習用）

```python
fibonacci_memoized(n)
```

**注意**: n < 1000 に制限
- Pythonの再帰深度制限（デフォルト約1000）に注意
- 学習目的やプロトタイピングに有用

## ファイル構成

- `fibonacci.py` - 3つの実装とデモコード
- `test_fibonacci.py` - 包括的なテストスイート
- `fibonacci_README.md` - このドキュメント

## 実装の根拠

本実装は以下の情報源を参考にしています:

1. **Python公式ドキュメント** - `functools.lru_cache`の使用法
2. **Real Python** - フィボナッチ実装のベストプラクティス
3. **アルゴリズム理論** - 行列累乗による O(log n) 実装

## ライセンス

このコードは教育目的で自由に使用できます。
