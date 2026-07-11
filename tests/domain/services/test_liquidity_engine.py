"""
Tests para LiquidityEngine.
"""

from domain.services.liquidity_engine import LiquidityEngine, LiquidityInput


def test_liquidity_engine_basic():
    engine = LiquidityEngine()

    input_data = LiquidityInput(
        daily_volume=50000,
        total_sell_volume_remain=200000,
        sell_order_count=20,
        buy_order_count=35
    )

    result = engine.calculate(input_data)

    assert result.is_valid
    assert result.value.liquidity_score > 0
    assert result.value.depth_score > 0


def test_liquidity_engine_zero_volume_gives_zero_score_regardless_of_depth():
    """
    Regresión del bug de "order book fantasma" (MATH-002 v1.4): un ítem
    sin NINGÚN volumen diario real debe tener liquidity_score=0, sin
    importar cuánta profundidad (volume_remain) tenga acumulada en el
    book. Antes del fix (promedio ponderado 60/40), esto podía dar hasta
    40/100 solo por profundidad estancada.
    """
    engine = LiquidityEngine()

    input_data = LiquidityInput(
        daily_volume=0,
        total_sell_volume_remain=50_000_000,  # profundidad máxima (D_REF)
        sell_order_count=5,
        buy_order_count=5,
    )

    result = engine.calculate(input_data)

    assert result.value.liquidity_score == 0.0
    assert result.validation_status == "Degraded"


def test_liquidity_engine_degrades_confidence_without_volume_evidence():
    """Sin evidencia de volumen, el resultado debe marcarse Degraded (no Invalid:
    el cálculo sigue siendo matemáticamente correcto, solo incompleto)."""
    engine = LiquidityEngine()

    result = engine.calculate(LiquidityInput(
        daily_volume=0,
        total_sell_volume_remain=1000,
        sell_order_count=1,
        buy_order_count=1,
    ))

    assert result.validation_status == "Degraded"
    assert result.confidence < 90.0


def test_liquidity_engine_real_turnover_scores_higher_than_pure_depth():
    """Dos ítems con la misma profundidad: el que tiene turnover real debe
    puntuar más alto que el que no tiene ninguno."""
    engine = LiquidityEngine()

    with_turnover = engine.calculate(LiquidityInput(
        daily_volume=5000, total_sell_volume_remain=10_000_000,
        sell_order_count=10, buy_order_count=10,
    ))
    without_turnover = engine.calculate(LiquidityInput(
        daily_volume=0, total_sell_volume_remain=10_000_000,
        sell_order_count=10, buy_order_count=10,
    ))

    assert with_turnover.value.liquidity_score > without_turnover.value.liquidity_score
    assert without_turnover.value.liquidity_score == 0.0
