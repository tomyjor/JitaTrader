"""
Application Use Case: DetectOpportunitiesUseCase

Orquesta la obtención de datos de mercado (vía los ports de dominio) y la
evaluación de cada type_id a través de OpportunityEngine. No contiene
lógica de negocio propia -- solo coordina repositorios + motor y arma un
reporte legible de qué se evaluó, qué se excluyó y por qué.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

from domain.ports.market_repository import MarketRepository
from domain.ports.type_repository import TypeRepository
from domain.services.opportunity_engine import OpportunityEngine, OpportunityInput
from domain.value_objects.tax_profile import TaxProfile


@dataclass
class DetectOpportunitiesRequest:
    type_ids: List[int]
    region_id: int
    tax_profile: TaxProfile


@dataclass
class DetectOpportunitiesResult:
    opportunities: list = field(default_factory=list)
    skipped: List[Tuple[int, str]] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    # Ranking completo (TODO lo que tuvo evidencia suficiente), ordenado por score desc,
    # SIN filtrar por min_score. Existe para que el modo Discovery pueda mostrar
    # "las mejores disponibles" aunque ninguna supere el umbral.
    ranked_all: list = field(default_factory=list)


class DetectOpportunitiesUseCase:
    def __init__(
        self,
        market_repository: MarketRepository,
        type_repository: TypeRepository,
        opportunity_engine: OpportunityEngine,
    ):
        self.market_repository = market_repository
        self.type_repository = type_repository
        self.opportunity_engine = opportunity_engine

    def execute(
        self,
        request: DetectOpportunitiesRequest,
        min_score: float = 55.0,
        max_results: int = 50,
    ) -> DetectOpportunitiesResult:
        """
        Evalúa cada type_id de la request y devuelve las oportunidades con
        score >= min_score (hasta max_results), además del ranking
        completo sin filtrar (`ranked_all`, usado por el modo Discovery
        como fallback) y la lista de ítems excluidos con motivo.
        """
        raw_results = []
        skipped: List[Tuple[int, str]] = []

        for type_id in request.type_ids:
            type_info = self.type_repository.get(type_id)
            if type_info is None:
                skipped.append((type_id, "type_id no existe en SDE"))
                continue

            snapshot = self.market_repository.get_current_snapshot(type_id, request.region_id)
            if snapshot is None:
                skipped.append((type_id, "sin order book completo (falta buy o sell)"))
                continue

            sell_count = buy_count = 0
            total_sell_remain = 0.0
            total_buy_remain = 0.0

            # Estos métodos extra están en la impl SQLite (no en el Port
            # abstracto todavía, ver comentario en SQLiteMarketRepository).
            if hasattr(self.market_repository, "order_counts"):
                sell_count, buy_count = self.market_repository.order_counts(type_id, request.region_id)
            if hasattr(self.market_repository, "total_sell_volume_remain"):
                total_sell_remain = self.market_repository.total_sell_volume_remain(type_id, request.region_id)
            if hasattr(self.market_repository, "total_buy_volume_remain"):
                total_buy_remain = self.market_repository.total_buy_volume_remain(type_id, request.region_id)

            if sell_count == 0 and buy_count == 0:
                skipped.append((type_id, "order book vacío"))
                continue

            opportunity_input = OpportunityInput(
                type_id=type_id,
                type_name=type_info.get("name", f"Type-{type_id}"),
                region_id=request.region_id,
                buy_price=snapshot.buy_price,
                sell_price=snapshot.sell_price,
                daily_volume=snapshot.daily_volume,
                total_sell_volume_remain=total_sell_remain,
                total_buy_volume_remain=total_buy_remain,
                sell_order_count=sell_count,
                buy_order_count=buy_count,
                tax_profile=request.tax_profile,
            )

            try:
                result = self.opportunity_engine.detect(opportunity_input)
                raw_results.append(result)
            except Exception as e:
                skipped.append((type_id, f"error en motores: {str(e)}"))

        raw_results.sort(key=lambda r: r.value.score, reverse=True)

        filtered = [r for r in raw_results if r.value.score >= min_score]
        top = filtered[:max_results]

        summary = {
            "type_ids_evaluados": len(request.type_ids),
            "con_evidencia_suficiente": len(raw_results),
            "oportunidades": len(top),
            "min_score_usado": min_score,
        }

        return DetectOpportunitiesResult(
            opportunities=top,
            skipped=skipped,
            summary=summary,
            ranked_all=raw_results,
        )
