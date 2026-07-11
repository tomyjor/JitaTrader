"""
Implementación en memoria de TypeRepository (útil para tests y prototipos).
"""

from typing import Optional, Dict
from domain.ports.type_repository import TypeRepository


class InMemoryTypeRepository(TypeRepository):
    def __init__(self, data: Dict[int, Dict] = None):
        self._data = data or {}

    def get(self, type_id: int) -> Optional[Dict]:
        return self._data.get(type_id)

    def get_name(self, type_id: int) -> Optional[str]:
        item = self._data.get(type_id)
        return item.get("name") if item else None

    def add(self, type_id: int, name: str, **kwargs):
        self._data[type_id] = {"name": name, **kwargs}
