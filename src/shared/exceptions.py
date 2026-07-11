"""
Excepciones de Dominio para JitaTrader v2.
"""

class DomainError(Exception):
    """Error base de dominio."""
    pass


class InvalidMarketDataError(DomainError):
    pass


class CalculationError(DomainError):
    pass
