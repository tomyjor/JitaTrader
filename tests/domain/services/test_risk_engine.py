"""
Tests para RiskEngine.
"""

from domain.value_objects.liquidity import Liquidity
from domain.services.risk_engine import RiskEngine, RiskInput


def test_risk_engine_calculation():
    engine = RiskEngine()

    liquidity = Liquidity(
        daily_volume=50000,
        liquidity_score=65.0,
        depth_score=70.0
    )

    input_data = RiskInput(
        roi_percent=45.0,
        liquidity=liquidity,
        competition_score=55.0,
        capital_required=None  # No lo usamos en este test
    )

    result = engine.calculate(input_data)

    assert result.is_valid
    assert result.value.overall_risk_score > 0
    assert result.value.risk_level in ["Low", "Medium", "High", "Critical"]
