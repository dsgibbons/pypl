"""Free-function module. Exercises the <<namespace>> rendering."""


def compute_tax(amount: int, rate_percent: int) -> int:
    return (amount * rate_percent) // 100


def log_sale(message: str) -> None:
    print(f"[sale] {message}")
