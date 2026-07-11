"""
Value Object: Liquidity
Métrica pura de liquidez según MATH-002 v1.3.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Liquidity:
    daily_volume: float
    liquidity_score: float      # 0-100
    depth_score: float          # 0-100

    def __post_init__(self):
        if self.daily_volume < 0:
            raise ValueError("daily_volume cannot be negative")
        if not (0 <= self.liquidity_score <= 100):
            raise ValueError("liquidity_score must be between 0 and 100")
        if not (0 <= self.depth_score <= 100):
            raise ValueError("depth_score must be between 0 and 100")
