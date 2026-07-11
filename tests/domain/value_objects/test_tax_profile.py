"""
Tests para TaxProfile.
"""

import pytest
from domain.value_objects.tax_profile import TaxProfile


def test_tax_profile_creation():
    tax = TaxProfile(broker_fee_rate=0.03, sales_tax_rate=0.036)
    assert tax.broker_fee_rate == 0.03
    assert tax.total_sell_fee_rate == 0.066


def test_tax_profile_invalid_rate():
    with pytest.raises(ValueError):
        TaxProfile(broker_fee_rate=1.5, sales_tax_rate=0.0)
