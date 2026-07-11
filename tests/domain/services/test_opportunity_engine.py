"""
Tests básicos para OpportunityEngine.
"""

from domain.value_objects.money import Money
from domain.value_objects.tax_profile import TaxProfile
from domain.value_objects.recommendation import RecommendationLevel
from domain.services.opportunity_engine import OpportunityEngine, OpportunityInput


TAX = TaxProfile(broker_fee_rate=0.03, sales_tax_rate=0.036)


def _make_input(buy, sell, daily_volume=0.0, sell_remain=500_000.0,
                 sell_count=3, buy_count=3, buy_remain=0.0):
    return OpportunityInput(
        type_id=1, type_name="Test Item", region_id=10000002,
        buy_price=Money(int(buy * 100)), sell_price=Money(int(sell * 100)),
        daily_volume=daily_volume, total_sell_volume_remain=sell_remain,
        total_buy_volume_remain=buy_remain,
        sell_order_count=sell_count, buy_order_count=buy_count,
        tax_profile=TAX,
    )


def test_opportunity_engine_detects_opportunity():
    engine = OpportunityEngine()

    input_data = OpportunityInput(
        type_id=34,
        type_name="Tritanium",
        region_id=10000002,
        buy_price=Money(300),
        sell_price=Money(450),
        daily_volume=50000,
        total_sell_volume_remain=120000,
        sell_order_count=25,
        buy_order_count=40,
        tax_profile=TAX
    )

    result = engine.detect(input_data)

    assert result.is_valid
    assert result.value.score > 0
    assert result.value.risk is not None
    assert result.value.liquidity is not None


def test_roi_component_no_longer_saturates_for_high_roi_items():
    """
    Regresión del bug reportado: ROI de 292%, 1558% y 3559% (con la
    misma liquidez/condiciones) deben producir scores DIFERENTES, no el
    mismo valor colapsado. La fórmula log_v1 saturaba a partir de ~139%
    de ROI.
    """
    engine = OpportunityEngine()

    inputs = [
        _make_input(buy=100, sell=380),   # ROI moderado-alto
        _make_input(buy=100, sell=1650),  # ROI muy alto
        _make_input(buy=100, sell=3650),  # ROI extremo
    ]
    scores = [engine.detect(inp).value.score for inp in inputs]

    # Estrictamente creciente: a mayor ROI (con todo lo demás igual),
    # el score debe ser mayor.
    assert scores[0] < scores[1] < scores[2], scores

    # Y con separación real, no un empate por redondeo.
    assert scores[2] - scores[0] > 2.0, scores


def test_recommendation_requires_real_liquidity_not_just_high_score():
    """
    Regresión del bug del badge: un ítem con ROI extremo pero SIN
    evidencia de volumen diario (order book potencialmente fantasma)
    nunca debe recibir RecommendationLevel.BUY, sin importar cuán alto
    sea su ROI.
    """
    engine = OpportunityEngine()

    ghost_book = _make_input(buy=100, sell=3650, daily_volume=0, sell_remain=50_000_000)
    result = engine.detect(ghost_book)

    assert result.value.recommendation != RecommendationLevel.BUY
    assert result.value.recommendation == RecommendationLevel.CAUTION_NO_VOLUME_DATA


def test_recommendation_buy_requires_score_and_liquidity_together():
    """Con ROI decente, liquidez real y bajo riesgo, sí debe recomendar compra."""
    engine = OpportunityEngine()

    healthy = _make_input(
        buy=100, sell=220, daily_volume=20000, sell_remain=30_000_000,
        sell_count=20, buy_count=20,
    )
    result = engine.detect(healthy)

    assert result.value.recommendation == RecommendationLevel.BUY
    assert result.value.is_buy_recommended is True


def test_score_breakdown_contributions_sum_to_final_score():
    """
    Chequeo de honestidad matemática: la suma de las contribuciones
    individuales del desglose debe coincidir con el score final (salvo
    un margen de redondeo de centésimas). Si esto falla, hay un bug de
    composición en OpportunityEngine.
    """
    engine = OpportunityEngine()
    result = engine.detect(_make_input(buy=100, sell=180, daily_volume=8000, sell_remain=10_000_000))

    breakdown = result.value.score_breakdown
    assert breakdown["formula_version"] == "log_v2"

    computed_sum = sum(c["contribution"] for c in breakdown["components"].values())
    assert abs(computed_sum - breakdown["final_score"]) < 0.5


def test_score_breakdown_always_present():
    engine = OpportunityEngine()
    result = engine.detect(_make_input(buy=100, sell=150))
    assert result.value.score_breakdown
    assert "components" in result.value.score_breakdown
    assert "recommendation" in result.value.score_breakdown
