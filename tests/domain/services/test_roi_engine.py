"""
Tests para ROIEngine.
"""

import pytest
from domain.value_objects.money import Money
from domain.value_objects.tax_profile import TaxProfile
from domain.services.roi_engine import ROIEngine, ROIInput


def test_roi_engine_basic_calculation():
    engine = ROIEngine()

    tax = TaxProfile(broker_fee_rate=0.03, sales_tax_rate=0.036)
    input_data = ROIInput(
        buy_price=Money(10000),   # 100 ISK
        sell_price=Money(15000),  # 150 ISK
        tax_profile=tax
    )

    result = engine.calculate(input_data)

    assert result.is_valid
    assert result.value.roi_percent > 0
    assert result.value.total_capital_required.amount_minor > 10000  # Incluye broker fee de compra


def test_roi_engine_negative_profit():
    engine = ROIEngine()

    tax = TaxProfile(broker_fee_rate=0.03, sales_tax_rate=0.036)
    input_data = ROIInput(
        buy_price=Money(20000),
        sell_price=Money(18000),
        tax_profile=tax
    )

    result = engine.calculate(input_data)

    assert result.value.roi_percent < 0
