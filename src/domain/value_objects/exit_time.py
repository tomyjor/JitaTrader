"""
Value Object: ExitTime
Estimación de tiempo de salida según MATH-005 v1.3.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExitTime:
    estimated_hours: float
    confidence: float = 80.0

    def __post_init__(self):
        if self.estimated_hours < 0:
            raise ValueError("estimated_hours cannot be negative")
        if not (0 <= self.confidence <= 100):
            raise ValueError("confidence must be between 0 and 100")
