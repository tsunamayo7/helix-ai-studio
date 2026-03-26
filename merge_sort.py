def merge_sort(lst: list) -> list:
    """マージソートでリストを昇順にソートする"""
    if len(lst) <= 1:
        return lst

    mid = len(lst) // 2
    left = merge_sort(lst[:mid])
    right = merge_sort(lst[mid:])

    return _merge(left, right)


def _merge(left: list, right: list) -> list:
    """ソート済みの2つのリストをマージする"""
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result


if __name__ == "__main__":
    test_cases = [
        [],
        [1],
        [3, 1, 2],
        [5, 3, 8, 1, 2, 7, 4, 6],
        [3, 3, 1, 1, 2, 2],
        [5, 4, 3, 2, 1],
    ]

    for tc in test_cases:
        print(f"{tc} -> {merge_sort(tc)}")
