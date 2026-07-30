from app.services.result import _build_distribution


def test_build_distribution_omits_bands_above_the_maximum_score():
    distribution = _build_distribution([0, 1, 2, 3], max_total=3)

    assert [item.range_label for item in distribution] == [
        "0~0",
        "1~1",
        "2~2",
        "3~3",
    ]
