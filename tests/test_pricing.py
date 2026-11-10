from vinted_bot.pricing import evaluate_deal


def test_not_a_deal_when_sample_too_small():
    result = evaluate_deal(prices=[10, 12, 15], item_price=5, threshold_percent=30)

    assert result.is_deal is False
    assert result.sample_size == 3


def test_is_deal_when_price_below_threshold():
    prices = [20, 25, 28, 30, 32, 35, 40]
    result = evaluate_deal(prices=prices, item_price=18, threshold_percent=30)

    assert result.sample_size == 7
    assert result.median_price == 30
    assert result.is_deal is True


def test_not_a_deal_when_price_above_threshold():
    prices = [20, 25, 28, 30, 32, 35, 40]
    result = evaluate_deal(prices=prices, item_price=25, threshold_percent=30)

    assert result.is_deal is False
    assert result.median_price == 30


def test_boundary_price_exactly_at_threshold_counts_as_deal():
    prices = [20, 25, 30, 35, 40]
    result = evaluate_deal(prices=prices, item_price=21, threshold_percent=30)

    assert result.median_price == 30
    assert result.is_deal is True
