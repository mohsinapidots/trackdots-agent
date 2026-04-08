def compute_backoff(
    failures: int,
    base: int = 10,
    factor: int = 2,
    max_backoff: int = 600,  # 10 minutes
) -> int:
    delay = base * (factor ** (failures - 1))
    return min(delay, max_backoff)
