"""
Tests para CompetitionEngine.
"""

from domain.services.competition_engine import CompetitionEngine, CompetitionInput


def test_competition_engine_basic():
    engine = CompetitionEngine()

    result = engine.calculate(CompetitionInput(
        buy_order_count=10,
        sell_order_count=10,
        total_buy_volume=1_000_000,
        total_sell_volume=1_000_000,
    ))

    assert result.is_valid
    assert 0 <= result.value.competition_score <= 100


def test_order_pressure_is_not_negligible_in_final_score():
    """
    Regresión del bug de unidades (MATH-003 v1.1): order_pressure vive
    en [0, 1] pero se pondera con 0.60 asumiendo escala [0, 100]. Sin el
    fix, pasar de "todos compradores" a "todos vendedores" cambiaba el
    competition_score en menos de 1 punto sobre 100 -- prácticamente
    invisible. Con el fix, ese mismo cambio debe mover el score de forma
    claramente perceptible.
    """
    engine = CompetitionEngine()

    all_buyers = engine.calculate(CompetitionInput(
        buy_order_count=100, sell_order_count=0,
        total_buy_volume=0, total_sell_volume=0,
    ))
    all_sellers = engine.calculate(CompetitionInput(
        buy_order_count=0, sell_order_count=100,
        total_buy_volume=0, total_sell_volume=0,
    ))

    delta = all_sellers.value.competition_score - all_buyers.value.competition_score
    # Con el fix, order_pressure pasa de ~0 a ~1, y pesa 0.60*100=60 puntos.
    assert delta > 50, f"delta demasiado chico ({delta}), sugiere que el bug de escala volvió"


def test_competition_score_stays_within_bounds():
    engine = CompetitionEngine()

    result = engine.calculate(CompetitionInput(
        buy_order_count=0,
        sell_order_count=500,
        total_buy_volume=0,
        total_sell_volume=1_000_000_000,
    ))

    assert 0 <= result.value.competition_score <= 100


def test_competition_input_has_no_price_spread_field():
    """
    Regresión de MATH-003 v1.2: price_spread_percent fue eliminado de
    CompetitionInput a propósito (señal invertida y redundante con
    roi_component/spread_quality en OpportunityEngine -- ver changelog
    en CompetitionEngine). Si alguien lo reintroduce sin pasar por el
    análisis documentado, este test lo va a marcar.
    """
    assert not hasattr(CompetitionInput, "price_spread_percent") or \
        "price_spread_percent" not in CompetitionInput.__dataclass_fields__
