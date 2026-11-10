from dataclasses import dataclass
from statistics import median

MIN_SAMPLE_SIZE = 5


@dataclass(frozen=True)
class DealResult:
    is_deal: bool
    median_price: float
    sample_size: int


def evaluate_deal(prices: list[float], item_price: float, threshold_percent: int) -> DealResult:
    sample_size = len(prices)
    if sample_size < MIN_SAMPLE_SIZE:
        return DealResult(is_deal=False, median_price=0.0, sample_size=sample_size)

    median_price = median(prices)
    cutoff = median_price * (1 - threshold_percent / 100)
    return DealResult(
        is_deal=item_price <= cutoff,
        median_price=median_price,
        sample_size=sample_size,
    )
