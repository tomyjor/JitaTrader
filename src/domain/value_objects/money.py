"""
Value Object: Money
Representa cantidades de dinero con precisión usando minor units (centavos para ISK).
"""

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class Money:
    """
    Cantidad de dinero inmutable.
    Se trabaja siempre en minor units (para ISK = centavos).
    """
    amount_minor: int
    currency: str = "ISK"

    def __post_init__(self):
        # Permitimos valores negativos (pérdidas, net profit negativo, etc.)
        # Esto es necesario en dominios financieros.
        if not self.currency:
            raise ValueError("Currency must be specified")

    @property
    def amount(self) -> float:
        """Devuelve el valor en unidades normales (ej: ISK completos)."""
        return self.amount_minor / 100

    def __str__(self) -> str:
        return f"{self.amount:,.2f} {self.currency}"

    def __add__(self, other: Self) -> Self:
        if self.currency != other.currency:
            raise ValueError("Cannot add Money with different currencies")
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: Self) -> Self:
        if self.currency != other.currency:
            raise ValueError("Cannot subtract Money with different currencies")
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def __mul__(self, scalar: float) -> Self:
        return Money(int(round(self.amount_minor * scalar)), self.currency)

    def __truediv__(self, scalar: float) -> Self:
        if scalar == 0:
            raise ZeroDivisionError("Cannot divide Money by zero")
        return Money(int(self.amount_minor / scalar), self.currency)
