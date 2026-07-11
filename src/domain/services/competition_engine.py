"""
Domain Service: CompetitionEngine
Evalúa presión competitiva según MATH-003 v1.2.

--------------------------------------------------------------------------
CHANGELOG v1.0 -> v1.1 (fix de unidades en order_pressure)
--------------------------------------------------------------------------
`order_pressure` está definido (MATH-003 §3.2) como una fracción en
[0, 1] (sell_order_count / total_orders). La fórmula de composición del
score, sin embargo, lo pondera con 0.50 asumiendo que está en la MISMA
escala 0-100 que `market_density`. Con la fórmula original tal cual
estaba escrita en código, `order_pressure` contribuía como máximo 0.5
puntos sobre un score declarado en [0, 100] -- en la práctica,
invisible frente a `market_density` (hasta 30 puntos). v1.1 escala
`order_pressure` a [0, 100] antes de ponderar.

--------------------------------------------------------------------------
CHANGELOG v1.1 -> v1.2 (se elimina price_spread_percent)
--------------------------------------------------------------------------
Análisis: un spread ancho (buy muy por debajo de sell) NO indica más
competencia -- indica menos. Un spread angosto es la firma de un mercado
con mucha presión competitiva (muchos vendedores compitiendo por ser el
más barato empujan el ask hacia abajo; muchos compradores compitiendo
por ser el que más paga empujan el bid hacia arriba). El propio MATH-003
lo confirma sin darse cuenta: define "higher score = higher competition
(harder to sell profitably)" -- bajo esa misma definición, un spread
angosto (margen exprimido por competencia) debería subir el score, y uno
ancho (margen capturado sin disputa) debería bajarlo. La fórmula v1.1
sumaba `price_spread_percent` con signo POSITIVO: exactamente invertido
respecto a la propia definición del documento.

Invertir el signo no alcanzaba como solución: el spread ya alimenta el
score final en otros dos lugares de `OpportunityEngine`
(`roi_component`, derivado del mismo spread neto de fees, y
`spread_quality`, el mismo spread bruto). Sumarlo una tercera vez acá
-- aunque con signo corregido -- hace que un mismo dato crudo empuje el
score en tres componentes con roles distintos, dos premiando el spread
ancho y uno castigándolo. Eso rompe la transparencia del desglose: dos
filas que en el fondo son la misma variable, tirando en direcciones
opuestas, sin explicación visible para el usuario.

v1.2 elimina `price_spread_percent` de este motor. "Competencia" pasa a
medir exclusivamente estructura del order book (cuántos rivales activos,
cuánta profundidad total) -- lo que ya hacían `order_pressure` y
`market_density` de forma honesta. El precio/margen sigue siendo
responsabilidad exclusiva de ROIEngine y del componente de spread en
OpportunityEngine, no de CompetitionEngine. El peso que tenía este
término (0.20) se redistribuye entre los otros dos: order_pressure
0.50 -> 0.60, market_density 0.30 -> 0.40.

Nota práctica: `price_spread_percent` nunca estuvo conectado en la
práctica (OpportunityEngine siempre lo dejaba en su default 0.0), así
que este cambio no altera ningún resultado observable hoy -- solo
formaliza el comportamiento real y saca un parámetro que quedaba ahí
invitando a conectarlo mal en el futuro.
"""

from dataclasses import dataclass

from domain.value_objects.competition import Competition
from domain.value_objects.analysis_result import AnalysisResult


@dataclass(frozen=True)
class CompetitionInput:
    """Datos crudos de order book necesarios para evaluar competencia estructural."""

    buy_order_count: int
    sell_order_count: int
    total_buy_volume: float
    total_sell_volume: float


class CompetitionEngine:
    """
    Motor de evaluación de competencia.
    Implementa MATH-003 v1.2 (ver changelog del módulo).

    Mide exclusivamente estructura del order book: cuántos vendedores
    compiten entre sí (`order_pressure`) y qué tan denso es el mercado
    (`market_density`). Deliberadamente NO considera precio/spread --
    eso es responsabilidad de ROIEngine y del componente de spread en
    OpportunityEngine.
    """

    #: Volumen total (buy + sell) que se considera "mercado saturado" = 100.
    DENSITY_REFERENCE = 100_000_000.0

    def calculate(self, input_data: CompetitionInput) -> AnalysisResult[Competition]:
        total_orders = input_data.buy_order_count + input_data.sell_order_count + 1
        order_pressure = input_data.sell_order_count / total_orders

        total_volume = input_data.total_buy_volume + input_data.total_sell_volume
        market_density = min((total_volume / self.DENSITY_REFERENCE) * 100, 100.0)

        # order_pressure vive en [0, 1]: se escala a [0, 100] antes de
        # ponderar (fix v1.1). Pesos redistribuidos tras sacar
        # price_spread_percent en v1.2 (ver changelog del módulo).
        competition_score = (
            (order_pressure * 100 * 0.60) +
            (market_density * 0.40)
        )
        competition_score = min(max(competition_score, 0.0), 100.0)

        result = Competition(
            competition_score=round(competition_score, 2),
            order_pressure=round(order_pressure, 4),
            market_density=round(market_density, 2),
        )

        return AnalysisResult(
            value=result,
            confidence=88.0,
            evidence_count=1,
            validation_status="Valid",
        )
