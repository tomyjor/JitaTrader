"""
Value Object: Competition
Presión competitiva según MATH-003.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Competition:
    competition_score: float     # 0-100 (más alto = más competencia)
    order_pressure: float
    market_density: float

    def __post_init__(self):
        if not (0 <= self.competition_score <= 100):
            raise ValueError("competition_score must be between 0 and 100")
