"""
Port: MarketRepository
Interfaz abstracta para obtener datos de mercado.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from domain.value_objects.money import Money


class MarketSnapshot:
    """Representación simplificada de un snapshot de mercado."""
    def __init__(self, type_id: int, buy_price: Money, sell_price: Money, daily_volume: float):
        self.type_id = type_id
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.daily_volume = daily_volume


class MarketRepository(ABC):
    """
    Puerto abstracto para acceder a datos de mercado.
    Las implementaciones concretas (ESI, SQLite, CSV, etc.) van en Infrastructure.
    """

    @abstractmethod
    def get_current_snapshot(self, type_id: int, region_id: int) -> Optional[MarketSnapshot]:
        """Obtiene el snapshot actual de un ítem en una región."""
        pass

    @abstractmethod
    def get_daily_volume(self, type_id: int, region_id: int) -> float:
        """Obtiene el volumen diario promedio."""
        pass
