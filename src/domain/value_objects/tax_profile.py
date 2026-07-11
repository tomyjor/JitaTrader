"""
Value Object: TaxProfile
Representa las tasas de impuestos aplicables a una transacción en EVE Online.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TaxProfile:
    """
    Tasas de impuestos derivadas de skills + standings + estación.
    """
    broker_fee_rate: float   # Ej: 0.03 (3%)
    sales_tax_rate: float    # Ej: 0.036 (3.6%)

    def __post_init__(self):
        if not (0 <= self.broker_fee_rate <= 1):
            raise ValueError("broker_fee_rate must be between 0 and 1")
        if not (0 <= self.sales_tax_rate <= 1):
            raise ValueError("sales_tax_rate must be between 0 and 1")

    @property
    def total_sell_fee_rate(self) -> float:
        """Tasa total aplicada en la venta."""
        return self.broker_fee_rate + self.sales_tax_rate

    def __str__(self) -> str:
        return f"Broker: {self.broker_fee_rate*100:.1f}%, Sales Tax: {self.sales_tax_rate*100:.1f}%"
