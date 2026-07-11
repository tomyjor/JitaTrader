"""
Domain Service: RiskEngine
Calcula el riesgo combinado según MATH-004 v1.0.

Revisado en este sprint: la fórmula es fiel al spec (MATH-004 §3.2) y no
presenta el bug de saturación reportado en OpportunityEngine (el término
`profitability_risk = max(0, 50 - roi_percent)` cae a 0 rápido por
diseño -- una vez que el ROI supera el umbral mínimo aceptable, más ROI
no reduce más el riesgo de rentabilidad, lo cual es una decisión de
modelado razonable, no un bug). No se modificó la lógica.
"""

from dataclasses import dataclass
from typing import Dict
from domain.value_objects.risk import Risk
from domain.value_objects.analysis_result import AnalysisResult
from domain.value_objects.money import Money
from domain.value_objects.liquidity import Liquidity


@dataclass(frozen=True)
class RiskInput:
    """Datos de entrada para RiskEngine (composición de ROI + Liquidez + Competencia)."""

    roi_percent: float
    liquidity: Liquidity
    competition_score: float

    #: Reservado para uso futuro (riesgo de concentración de capital a
    #: nivel portfolio, ver MATH-007). No participa todavía en el cálculo
    #: de `overall_risk_score` -- ni en este código ni en el spec MATH-004.
    capital_required: Money
    user_risk_tolerance: float = 50.0   # 0-100 (más alto = más tolerante)


class RiskEngine:
    """
    Motor de evaluación de riesgo.
    Combina Profitability + Liquidity + Competition.
    """

    def calculate(self, input_data: RiskInput) -> AnalysisResult[Risk]:
        # Componentes de riesgo (0-100, donde 100 = máximo riesgo)
        profitability_risk = max(0, 50 - input_data.roi_percent)
        liquidity_risk = 100 - input_data.liquidity.liquidity_score
        competition_risk = input_data.competition_score

        # Ponderación según MATH-004
        overall_risk = (
            (profitability_risk * 0.35) +
            (liquidity_risk * 0.40) +
            (competition_risk * 0.25)
        )

        overall_risk = min(max(overall_risk, 0), 100)

        # Determinar nivel de riesgo
        if overall_risk < 25:
            risk_level = "Low"
        elif overall_risk < 50:
            risk_level = "Medium"
        elif overall_risk < 75:
            risk_level = "High"
        else:
            risk_level = "Critical"

        components: Dict[str, float] = {
            "profitability": round(profitability_risk, 2),
            "liquidity": round(liquidity_risk, 2),
            "competition": round(competition_risk, 2)
        }

        result = Risk(
            overall_risk_score=round(overall_risk, 2),
            components=components,
            risk_level=risk_level
        )

        return AnalysisResult(
            value=result,
            confidence=85.0,
            evidence_count=3,
            validation_status="Valid"
        )
