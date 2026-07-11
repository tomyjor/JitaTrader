"""
Corré esto desde la raíz del proyecto:
    PYTHONPATH=src python scripts/run_detection.py

Pipeline completo: SQLiteTypeRepository + SQLiteMarketRepository (datos
REALES de database/trader.db) -> DetectOpportunitiesUseCase -> OpportunityEngine.

Si tracked_types está vacía o market_orders/market_history no tienen datos
para esos type_ids todavía, este script te lo va a decir explícitamente
en vez de mostrar resultados fabricados -- es la prueba de que el
Principio II (Deterministic Explainability) se sostiene también en el
wiring, no solo en la matemática interna de cada motor.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from domain.value_objects.tax_profile import TaxProfile
from domain.services.opportunity_engine import OpportunityEngine
from infrastructure.repositories.sqlite_type_repository import SQLiteTypeRepository
from infrastructure.repositories.sqlite_market_repository import SQLiteMarketRepository
from application.use_cases.detect_opportunities_use_case import (
    DetectOpportunitiesUseCase,
    DetectOpportunitiesRequest,
)

REGION_ID_JITA = 10000002  # The Forge


def main():
    db_path = Path(__file__).resolve().parent.parent / "database" / "trader.db"
    type_repo = SQLiteTypeRepository(db_path=db_path)
    market_repo = SQLiteMarketRepository(db_path=db_path)

    tracked = type_repo.tracked_type_ids()

    if not tracked:
        print("⚠ No hay ningún type_id en tracked_types todavía.")
        print("  Agregá alguno con: python scripts/track_type.py \"nombre del producto\"")
        return

    print(f"Evaluando {len(tracked)} producto(s) trackeado(s) en región {REGION_ID_JITA}...\n")

    use_case = DetectOpportunitiesUseCase(
        market_repository=market_repo,
        type_repository=type_repo,
        opportunity_engine=OpportunityEngine(),
    )

    tax = TaxProfile(broker_fee_rate=0.03, sales_tax_rate=0.036)
    request = DetectOpportunitiesRequest(type_ids=tracked, region_id=REGION_ID_JITA, tax_profile=tax)
    result = use_case.execute(request)

    print("=== Resumen ===")
    for k, v in result.summary.items():
        print(f"  {k}: {v}")

    if result.skipped:
        print("\n=== Excluidos (evidencia insuficiente) ===")
        for type_id, motivo in result.skipped:
            name = type_repo.get_name(type_id) or f"type_id {type_id}"
            print(f"  {name}: {motivo}")

    if result.opportunities:
        print("\n=== Oportunidades ===")
        for r in result.opportunities:
            o = r.value
            print(
                f"  {o.type_name:<35} score={o.score:6.2f}  "
                f"ROI={o.roi_percent:6.2f}%  confianza={r.confidence:.0f}%"
            )
    elif result.summary["con_evidencia_suficiente"] > 0:
        print(
            f"\nSe evaluaron {result.summary['con_evidencia_suficiente']} producto(s) con datos "
            "reales, pero ninguno superó el umbral de score. Esto es un resultado válido, no "
            "un error -- probá con --min-score más bajo si querés ver el detalle igual."
        )
    else:
        print("\nNinguno de los productos trackeados tiene evidencia de mercado todavía.")
        print("Corré el importador de market_history/market_orders contra ESI para esos")
        print("productos antes de esperar resultados acá.")


if __name__ == "__main__":
    main()
