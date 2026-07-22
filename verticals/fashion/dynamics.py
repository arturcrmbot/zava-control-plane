from __future__ import annotations


HERO_SALE_TICKS = frozenset({6, 10, 14, 18})
ORDINARY_TICK_MINUTES = 3


def customer_number(tick: int, customer_count: int) -> int:
    return ((tick * 17) % customer_count) + 1


def store_number(tick: int, store_count: int) -> int:
    return ((tick * 5) % store_count) + 1


def should_cancel(tick: int) -> bool:
    return tick % 7 == 0


def should_receive_return(tick: int) -> bool:
    return tick % 5 == 0


def should_receive_delivery(tick: int) -> bool:
    return tick % 9 == 0
