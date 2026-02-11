"""
フィボナッチ数列の実装

3つのアプローチを提供:
1. lru_cache版: メモ化による自動最適化（推奨: n < 10^6）
2. イテレーティブ版: O(n)時間・O(1)空間の最適実装（推奨: 汎用）
3. 行列累乗版: O(log n)時間の超高速実装（推奨: n > 10^6）
"""

from functools import lru_cache
from typing import Tuple


# ============================================================
# 実装1: メモ化再帰版（@lru_cache）
# ============================================================
@lru_cache(maxsize=None)
def fibonacci_memoized(n: int) -> int:
    """
    メモ化を使ったフィボナッチ数列の計算

    Parameters
    ----------
    n : int
        非負の整数インデックス

    Returns
    -------
    int
        n番目のフィボナッチ数

    Raises
    ------
    ValueError
        nが負の場合

    Notes
    -----
    - 時間計算量: O(n)（各値は1回だけ計算）
    - 空間計算量: O(n)（キャッシュ + 再帰スタック）
    - 推奨範囲: n < 10,000（再帰スタック制限のため）

    Examples
    --------
    >>> fibonacci_memoized(0)
    0
    >>> fibonacci_memoized(10)
    55
    >>> fibonacci_memoized(100)
    354224848179261915075
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n < 2:
        return n
    return fibonacci_memoized(n - 1) + fibonacci_memoized(n - 2)


# ============================================================
# 実装2: イテレーティブ版（動的計画法）
# ============================================================
def fibonacci_iterative(n: int) -> int:
    """
    イテレーティブなフィボナッチ数列の計算（推奨実装）

    Parameters
    ----------
    n : int
        非負の整数インデックス

    Returns
    -------
    int
        n番目のフィボナッチ数

    Raises
    ------
    ValueError
        nが負の場合

    Notes
    -----
    - 時間計算量: O(n)
    - 空間計算量: O(1)（2つの変数のみ使用）
    - 推奨範囲: 全ての実用範囲（n = 0 ~ 10^6 以上）
    - スタックオーバーフローのリスクなし
    - 最もシンプルで保守しやすい実装

    Examples
    --------
    >>> fibonacci_iterative(0)
    0
    >>> fibonacci_iterative(10)
    55
    >>> fibonacci_iterative(1000)
    43466557686937456435688527675040625802564660517371780402481729089536555417949051890403879840079255169295922593080322634775209689623239873322471161642996440906533187938298969649928516003704476137795166849228875
    """
    if n < 0:
        raise ValueError("n must be non-negative")

    # 前項(a)と現在項(b)を初期化
    a, b = 0, 1

    # n回のイテレーションで計算
    for _ in range(n):
        a, b = b, a + b

    return a


# ============================================================
# 実装3: 行列累乗版（高速倍乗法）
# ============================================================
def _matrix_multiply_2x2(
    m1: Tuple[int, int, int, int],
    m2: Tuple[int, int, int, int]
) -> Tuple[int, int, int, int]:
    """2x2行列の乗算"""
    a, b, c, d = m1
    e, f, g, h = m2
    return (
        a * e + b * g,
        a * f + b * h,
        c * e + d * g,
        c * f + d * h
    )


def _matrix_power(n: int) -> Tuple[int, int, int, int]:
    """
    行列 [[1, 1], [1, 0]] のn乗を計算

    繰り返し二乗法を使用してO(log n)で計算
    """
    if n == 0:
        return (1, 0, 0, 1)  # 単位行列
    if n == 1:
        return (1, 1, 1, 0)

    # n が偶数の場合: M^n = (M^(n/2))^2
    # n が奇数の場合: M^n = M * M^(n-1)
    if n % 2 == 0:
        half = _matrix_power(n // 2)
        return _matrix_multiply_2x2(half, half)
    else:
        return _matrix_multiply_2x2((1, 1, 1, 0), _matrix_power(n - 1))


def fibonacci_matrix(n: int) -> int:
    """
    行列累乗を使った超高速フィボナッチ数列の計算

    Parameters
    ----------
    n : int
        非負の整数インデックス

    Returns
    -------
    int
        n番目のフィボナッチ数

    Raises
    ------
    ValueError
        nが負の場合

    Notes
    -----
    - 時間計算量: O(log n)
    - 空間計算量: O(log n)（再帰スタック）
    - 推奨範囲: n > 10^6（大きなnで真価を発揮）
    - 数学的背景: [[F(n+1), F(n)], [F(n), F(n-1)]] = [[1,1],[1,0]]^n

    Examples
    --------
    >>> fibonacci_matrix(0)
    0
    >>> fibonacci_matrix(10)
    55
    >>> fibonacci_matrix(1000000)  # 100万番目も高速計算可能
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0

    # [[1,1],[1,0]]^n の右上要素がF(n)
    result_matrix = _matrix_power(n)
    return result_matrix[1]  # (0, 1)要素 = F(n)


# ============================================================
# デフォルト実装（汎用性を重視）
# ============================================================
def fibonacci(n: int) -> int:
    """
    フィボナッチ数列の計算（デフォルト実装）

    汎用性とシンプルさを重視し、イテレーティブ版を採用

    Parameters
    ----------
    n : int
        非負の整数インデックス

    Returns
    -------
    int
        n番目のフィボナッチ数

    See Also
    --------
    fibonacci_iterative : このデフォルト実装の本体
    fibonacci_memoized : メモ化再帰版
    fibonacci_matrix : 行列累乗版（超高速）
    """
    return fibonacci_iterative(n)


if __name__ == "__main__":
    # デモンストレーション
    print("=== フィボナッチ数列の実装比較 ===\n")

    test_values = [0, 1, 10, 20, 50, 100]

    print("小規模テスト（n = 0, 1, 10, 20, 50, 100）")
    print("-" * 60)
    for n in test_values:
        result = fibonacci(n)
        print(f"fibonacci({n:3d}) = {result}")

    print("\n\n各実装の性能比較")
    print("-" * 60)

    import time

    # n=500でテスト（メモ化版の再帰制限を考慮）
    n_test_small = 500

    # イテレーティブ版（n=500）
    start = time.time()
    result_iter_small = fibonacci_iterative(n_test_small)
    time_iter_small = time.time() - start
    print(f"[n={n_test_small}]")
    print(f"  イテレーティブ版: {time_iter_small*1000:.3f}ms")

    # メモ化版（キャッシュクリア、n=500）
    fibonacci_memoized.cache_clear()
    start = time.time()
    result_memo = fibonacci_memoized(n_test_small)
    time_memo = time.time() - start
    print(f"  メモ化版:         {time_memo*1000:.3f}ms")

    # 行列累乗版（n=500）
    start = time.time()
    result_matrix_small = fibonacci_matrix(n_test_small)
    time_matrix_small = time.time() - start
    print(f"  行列累乗版:       {time_matrix_small*1000:.3f}ms")

    # 結果の一致確認
    assert result_iter_small == result_memo == result_matrix_small

    # 大規模テスト（n=10000）: イテレーティブ版と行列累乗版のみ
    n_test_large = 10000
    print(f"\n[n={n_test_large}] ※メモ化版は再帰制限により除外")

    start = time.time()
    result_iter_large = fibonacci_iterative(n_test_large)
    time_iter_large = time.time() - start
    print(f"  イテレーティブ版: {time_iter_large*1000:.3f}ms")

    start = time.time()
    result_matrix_large = fibonacci_matrix(n_test_large)
    time_matrix_large = time.time() - start
    print(f"  行列累乗版:       {time_matrix_large*1000:.3f}ms (O(log n)の威力)")

    assert result_iter_large == result_matrix_large
    print(f"\n全実装で結果が一致: F({n_test_small}) = {len(str(result_iter_small))}桁の数")
    print(f"F({n_test_large}) = {len(str(result_iter_large))}桁の数")
