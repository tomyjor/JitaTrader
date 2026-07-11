"""
Domain Service: ExitTimeEngine
Calcula tiempo estimado de salida según MATH-005 v1.3.
"""

from dataclasses import dataclass
from domain.value_objects.exit_time import ExitTime
from domain.value_objects.analysis_result import AnalysisResult


@dataclass(frozen=True)
class ExitTimeInput:
    position_size: float
    daily_volume: float
    total_sell_volume_remain: float


class ExitTimeEngine:
    """
    Motor de estimación de tiempo de salida.
    Usa protección infinitesimal (1e-4) para ítems de baja rotación.
    """

    def calculate(self, input_data: ExitTimeInput) -> AnalysisResult[ExitTime]:
        if input_data.position_size <= 0:
            raise ValueError("position_size must be positive")

        # Protección contra volúmenes muy bajos (MATH-005 v1.3)
        min_denominator = 1e-4

        exit_time_volume = input_data.position_size / max(input_data.daily_volume / 24, min_denominator)
        exit_time_depth = input_data.position_size / max(input_data.total_sell_volume_remain, min_denominator)

        # Tomamos el valor más conservador
        estimated_hours = max(exit_time_volume, exit_time_depth)

        result = ExitTime(
            estimated_hours=round(estimated_hours, 2),
            confidence=75.0
        )

        return AnalysisResult(
            value=result,
            confidence=75.0,
            evidence_count=2,
            validation_status="Valid"
        )
