r"""
Importador de datos de mercado desde ESI (Jita).
Uso:
    set PYTHONPATH=src
    python scripts\import_esi_market_data.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from infrastructure.repositories.sqlite_type_repository import SQLiteTypeRepository
from infrastructure.esi.market_orders_importer import MarketOrdersImporter

REGION_ID_JITA = 10000002


def main():
    print("🚀 Iniciando importación de datos de mercado desde ESI (Jita)...\n")

    type_repo = SQLiteTypeRepository()
    tracked = type_repo.tracked_type_ids()

    if not tracked:
        print("⚠ No hay productos trackeados. Usá primero track_type.py")
        return

    print(f"Importando datos para {len(tracked)} productos trackeados...\n")

    orders_importer = MarketOrdersImporter()
    orders_importer.import_region_orders(REGION_ID_JITA, tracked)

    print("\n✅ Importación de órdenes completada.")
    print("   Ahora podés correr: run_detection.py")


if __name__ == "__main__":
    main()