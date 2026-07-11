"""
Domain Service: LiquidityEngine
Calcula liquidez según MATH-002 v1.4.

--------------------------------------------------------------------------
CHANGELOG v1.3 -> v1.4 (fix de "order book fantasma")
--------------------------------------------------------------------------
La versión anterior calculaba:

    liquidity_score = (volume_score * 0.60) + (depth_score * 0.40)

Un promedio ponderado deja que CUALQUIERA de los dos componentes cargue
con el score, incluso si el otro es cero. En la práctica esto significa
que un ítem SIN volumen diario real (daily_volume=0 -- por ejemplo porque
todavía no se importó `market_history`, o porque de verdad nadie lo
comercia) podía sacar hasta 40/100 de liquidez pura y exclusivamente por
tener muchas unidades *paradas* en el order book (volume_remain). Eso es,
por definición, un order book fantasma: hay cantidad ofertada, pero nadie
la está moviendo.

Esto no era un caso raro. Mientras `market_history` esté vacía (estado en
el que arranca el proyecto hasta correr el importador de historial),
volume_score es 0 para TODOS los ítems, así que liquidity_score terminaba
siendo depth_score*0.4 para la base completa -- el sistema recomendaba
comprando en base a profundidad estancada, no a liquidez real.

v1.4 reemplaza el promedio ponderado por una media geométrica:

    liquidity_score = sqrt(volume_score * depth_score)

Con media geométrica, si cualquiera de los dos componentes es 0, el
resultado es 0: no hay forma de que "profundidad sin movimiento" produzca
un score de liquidez positivo. Sigue siendo una fórmula pura, de una sola
línea, determinística -- no se sacrifica simplicidad por este fix.
"""

import math
from dataclasses import dataclass

from domain.value_objects.liquidity import Liquidity
from domain.value_objects.analysis_result import AnalysisResult


@dataclass(frozen=True)
class LiquidityInput:
    """Datos crudos de order book necesarios para evaluar liquidez."""

    #: Volumen diario negociado (unidades). 0.0 significa "sin evidencia
    #: de turnover reciente", nunca "asumimos un volumen típico".
    daily_volume: float

    #: Suma de volume_remain de todas las órdenes de venta activas.
    total_sell_volume_remain: float

    sell_order_count: int
    buy_order_count: int


class LiquidityEngine:
    """
    Motor de evaluación de liquidez.
    Implementa MATH-002 v1.4 (media geométrica, fix de "order book fantasma").
    """

    #: Volumen diario (unidades) que se considera "liquidez de referencia" = 100.
    VOLUME_REFERENCE = 10_000.0

    #: Volumen remanente en el book (unidades) que se considera "profundidad de referencia" = 100.
    DEPTH_REFERENCE = 50_000_000.0

    def calculate(self, input_data: LiquidityInput) -> AnalysisResult[Liquidity]:
        """
        Calcula liquidez pura a partir de volumen real y profundidad del book.

        Devuelve `validation_status="Degraded"` (con confidence reducida)
        cuando no hay NINGUNA evidencia de volumen diario -- no porque el
        cálculo sea inválido (liquidity_score=0 sigue siendo la lectura
        matemáticamente correcta), sino para que el caller pueda distinguir
        "confirmado ilíquido" de "no tenemos datos para saberlo todavía".
        """
        if input_data.daily_volume < 0:
            raise ValueError("daily_volume cannot be negative")
        if input_data.total_sell_volume_remain < 0:
            raise ValueError("total_sell_volume_remain cannot be negative")

        volume_score = min((input_data.daily_volume / self.VOLUME_REFERENCE) * 100, 100.0)
        depth_score = min((input_data.total_sell_volume_remain / self.DEPTH_REFERENCE) * 100, 100.0)

        # Media geométrica: gatea el score por evidencia REAL de turnover.
        # Ver changelog del módulo para el razonamiento completo.
        liquidity_score = math.sqrt(volume_score * depth_score)

        result = Liquidity(
            daily_volume=input_data.daily_volume,
            liquidity_score=round(liquidity_score, 2),
            depth_score=round(depth_score, 2),
        )

        has_volume_evidence = input_data.daily_volume > 0
        if not has_volume_evidence:
            return AnalysisResult(
                value=result,
                confidence=40.0,
                evidence_count=1,
                validation_status="Degraded",
                notes=(
                    "Sin evidencia de volumen diario (market_history vacío o "
                    "ítem sin trades reales recientes). liquidity_score=0 es "
                    "la lectura honesta, no un valor inventado."
                ),
            )

        return AnalysisResult(
            value=result,
            confidence=90.0,
            evidence_count=1,
            validation_status="Valid",
        )
