"""
Value Object: Opportunity
Representa una oportunidad de mercado ya analizada por OpportunityEngine.

Es deliberadamente un objeto de datos "tonto": toda la lógica de cálculo
(score, desglose, recomendación) vive en los motores de dominio, nunca
acá ni en la capa de presentación. Esto mantiene el Value Object como una
simple fotografía inmutable y consistente de un análisis ya hecho -- dos
instancias con los mismos campos son, por definición, la misma
oportunidad.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from domain.value_objects.money import Money
from domain.value_objects.risk import Risk
from domain.value_objects.liquidity import Liquidity
from domain.value_objects.recommendation import RecommendationLevel


@dataclass(frozen=True)
class Opportunity:
    """Resultado final e inmutable del análisis de una oportunidad de trading."""

    type_id: int
    type_name: str
    region_id: int

    buy_price: Money
    sell_price: Money

    roi_percent: float
    liquidity: Liquidity
    risk: Risk

    score: float = 0.0
    notes: Optional[str] = None

    #: Desglose completo y verificable del cálculo del score. Cada
    #: componente en `score_breakdown["components"]` incluye su valor
    #: crudo (0-100), su peso y su contribución real (raw_value * weight);
    #: la suma de todas las "contribution" es, por construcción, igual a
    #: `score` (con un margen de redondeo de centésimas). Ver
    #: `OpportunityEngine._build_score_breakdown`.
    score_breakdown: Dict[str, Any] = field(default_factory=dict)

    #: Recomendación calculada por el dominio (no por la UI). La capa de
    #: presentación solo debe leer estos dos campos para pintar el badge
    #: correspondiente -- nunca reimplementar sus propios umbrales.
    recommendation: RecommendationLevel = RecommendationLevel.NEUTRAL
    recommendation_reason: str = ""

    @property
    def is_buy_recommended(self) -> bool:
        """Azúcar sintáctica para la capa de presentación."""
        return self.recommendation.is_positive
