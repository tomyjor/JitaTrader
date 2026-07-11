"""
Port: TypeRepository
Interfaz para obtener metadata de ítems (del SDE).
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List


class TypeRepository(ABC):
    """
    Puerto abstracto para metadata de tipos de ítems.
    """

    @abstractmethod
    def get(self, type_id: int) -> Optional[Dict]:
        """Devuelve información básica de un type_id."""
        pass

    @abstractmethod
    def get_name(self, type_id: int) -> Optional[str]:
        pass

    @abstractmethod
    def tracked_type_ids(self) -> List[int]:
        pass
