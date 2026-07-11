"""
Value Object: AnalysisResult[T]
Wrapper genérico que envuelve cualquier resultado analítico con metadata.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


@dataclass(frozen=True)
class AnalysisResult(Generic[T]):
    """
    Resultado de un análisis con información de confianza y validación.
    """
    value: T
    confidence: float = 100.0          # 0-100
    evidence_count: int = 1
    validation_status: str = "Valid"   # Valid, Degraded, Invalid
    notes: Optional[str] = None

    def __post_init__(self):
        if not (0 <= self.confidence <= 100):
            raise ValueError("confidence must be between 0 and 100")
        if self.validation_status not in {"Valid", "Degraded", "Invalid"}:
            raise ValueError("Invalid validation_status")

    @property
    def is_valid(self) -> bool:
        return self.validation_status == "Valid"
