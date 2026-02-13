"""
フィボナッチ実装のテストスイート

正確性・性能・エッジケースを検証
"""

import pytest
import time
from fibonacci import (
    fibonacci,
    fibonacci_iterative,
    fibonacci_memoized,
    fibonacci_matrix
)


class TestFibonacciCorrectness:
    """正確性のテスト"""

    # 既知の正しい値
    KNOWN_VALUES = [
        (0, 0),
        (1, 1),
        (2, 1),
        (3, 2),
        (4, 3),
        (5, 5),
        (6, 8),
        (7, 13),
        (8, 21),
        (9, 34),
        (10, 55),
        (15, 610),
        (20, 6765),
        (30, 832040),
        (50, 12586269025),
        (100, 354224848179261915075),
    ]

    @pytest.mark.parametrize("n,expected", KNOWN_VALUES)
    def test_fibonacci_iterative(self, n, expected):
        """イテレーティブ版の正確性"""
        assert fibonacci_iterative(n) == expected

    @pytest.mark.parametrize("n,expected", KNOWN_VALUES)
    def test_fibonacci_memoized(self, n, expected):
        """メモ化版の正確性"""
        fibonacci_memoized.cache_clear()
        assert fibonacci_memoized(n) == expected

    @pytest.mark.parametrize("n,expected", KNOWN_VALUES)
    def test_fibonacci_matrix(self, n, expected):
        """行列累乗版の正確性"""
        assert fibonacci_matrix(n) == expected

    @pytest.mark.parametrize("n,expected", KNOWN_VALUES)
    def test_fibonacci_default(self, n, expected):
        """デフォルト実装の正確性"""
        assert fibonacci(n) == expected


class TestFibonacciEdgeCases:
    """エッジケースのテスト"""

    def test_negative_input_iterative(self):
        """負の入力でValueErrorが発生"""
        with pytest.raises(ValueError, match="non-negative"):
            fibonacci_iterative(-1)

    def test_negative_input_memoized(self):
        """負の入力でValueErrorが発生"""
        with pytest.raises(ValueError, match="non-negative"):
            fibonacci_memoized(-1)

    def test_negative_input_matrix(self):
        """負の入力でValueErrorが発生"""
        with pytest.raises(ValueError, match="non-negative"):
            fibonacci_matrix(-1)

    def test_large_n_iterative(self):
        """大きなn（1000）でも正常動作"""
        result = fibonacci_iterative(1000)
        assert result > 0
        # 1000番目のフィボナッチ数は約209桁
        assert len(str(result)) == 209

    def test_large_n_matrix(self):
        """行列累乗版は超大きなnでも高速"""
        result = fibonacci_matrix(10000)
        assert result > 0
        # 10000番目は約2090桁
        assert len(str(result)) > 2000


class TestFibonacciConsistency:
    """実装間の一貫性テスト"""

    TEST_RANGE = [0, 1, 5, 10, 20, 50, 100, 200, 500]

    @pytest.mark.parametrize("n", TEST_RANGE)
    def test_all_implementations_match(self, n):
        """全実装が同じ結果を返す"""
        fibonacci_memoized.cache_clear()

        result_iter = fibonacci_iterative(n)
        result_memo = fibonacci_memoized(n)
        result_matrix = fibonacci_matrix(n)

        assert result_iter == result_memo == result_matrix, \
            f"n={n}で実装間の不一致: iter={result_iter}, memo={result_memo}, matrix={result_matrix}"


class TestFibonacciPerformance:
    """性能テスト（参考）"""

    def test_iterative_performance_n1000(self):
        """イテレーティブ版: n=1000での性能"""
        start = time.time()
        result = fibonacci_iterative(1000)
        elapsed = time.time() - start

        assert result > 0
        assert elapsed < 0.01  # 10ms以内

    def test_memoized_performance_n500(self):
        """メモ化版: n=500での性能（初回）※再帰制限を考慮"""
        fibonacci_memoized.cache_clear()

        start = time.time()
        result = fibonacci_memoized(500)
        elapsed = time.time() - start

        assert result > 0
        assert elapsed < 0.1  # 100ms以内（再帰オーバーヘッド）

    def test_matrix_performance_n10000(self):
        """行列累乗版: n=10000での性能"""
        start = time.time()
        result = fibonacci_matrix(10000)
        elapsed = time.time() - start

        assert result > 0
        assert elapsed < 0.05  # 50ms以内（O(log n)の威力）

    def test_matrix_performance_n100000(self):
        """行列累乗版: n=100000での超高速計算"""
        start = time.time()
        result = fibonacci_matrix(100000)
        elapsed = time.time() - start

        assert result > 0
        # O(log n)なので、n=10000の時とほぼ同じ時間
        assert elapsed < 1.0  # 1秒以内


def test_docstring_exists():
    """全関数にdocstringが存在"""
    assert fibonacci.__doc__ is not None
    assert fibonacci_iterative.__doc__ is not None
    assert fibonacci_memoized.__doc__ is not None
    assert fibonacci_matrix.__doc__ is not None


if __name__ == "__main__":
    # pytest無しでも実行可能
    print("基本的な正確性テスト")
    print("-" * 60)

    test_cases = [(0, 0), (1, 1), (10, 55), (20, 6765)]

    for n, expected in test_cases:
        result = fibonacci(n)
        status = "✓" if result == expected else "✗"
        print(f"{status} fibonacci({n}) = {result} (expected: {expected})")

    print("\nエラーハンドリングテスト")
    print("-" * 60)

    try:
        fibonacci(-1)
        print("✗ 負の入力でValueErrorが発生しなかった")
    except ValueError:
        print("✓ 負の入力で正しくValueErrorが発生")

    print("\n実装間の一貫性テスト")
    print("-" * 60)

    n = 100
    fibonacci_memoized.cache_clear()
    r1 = fibonacci_iterative(n)
    r2 = fibonacci_memoized(n)
    r3 = fibonacci_matrix(n)

    if r1 == r2 == r3:
        print(f"✓ 全実装が一致: F({n}) = {r1}")
    else:
        print(f"✗ 実装間で不一致: iter={r1}, memo={r2}, matrix={r3}")

    print("\n性能比較（n=1000）")
    print("-" * 60)

    for name, func in [
        ("イテレーティブ", fibonacci_iterative),
        ("行列累乗", fibonacci_matrix)
    ]:
        if name == "メモ化":
            fibonacci_memoized.cache_clear()

        start = time.time()
        result = func(1000)
        elapsed = (time.time() - start) * 1000

        print(f"{name:12s}: {elapsed:6.2f}ms ({len(str(result))}桁)")

    print("\n全テスト完了！")
