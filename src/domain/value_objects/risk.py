"""
Value Object: Risk
Resultado de evaluación de riesgo según MATH-004.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Risk:
    overall_risk_score: float          # 0-100
    components: Dict[str, float]       # Ej: {"profitability": 35.0, "liquidity": 40.0, ...}
    risk_level: str                    # Low, Medium, High, Critical

    def __post_init__(self):
        if not (0 <= self.overall_risk_score <= 100):
            raise ValueError("overall_risk_score must be between 0 and 100")
        if self.risk_level not in {"Low", "Medium", "High", "Critical"}:
            raise ValueError("Invalid risk_level")
