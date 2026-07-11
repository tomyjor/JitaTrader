"""
Corré desde la raíz del proyecto:
    PYTHONPATH=src python scripts/track_type.py "shield extender"

Busca en item_types (52,744 productos reales del SDE) y te deja elegir
cuál trackear. No inventa nada: si no hay resultados, te lo dice y listo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infrastructure.repositories.sqlite_type_repository import SQLiteTypeRepository


def main():
    if len(sys.argv) < 2:
        print('Uso: python scripts/track_type.py "término de búsqueda"')
        return

    term = " ".join(sys.argv[1:])
    db_path = Path(__file__).resolve().parent.parent / "database" / "trader.db"
    repo = SQLiteTypeRepository(db_path=db_path)

    results = repo.search(term, limit=20)
    if not results:
        print(f"Sin resultados para '{term}'.")
        return

    for i, item in enumerate(results):
        print(f"  [{i}] {item['name']} (id={item['id']})")

    choice = input("\nElegí el número a trackear (o Enter para cancelar): ").strip()
    if not choice:
        print("Cancelado.")
        return

    try:
        idx = int(choice)
        chosen = results[idx]
    except (ValueError, IndexError):
        print("Opción inválida.")
        return

    repo.track(chosen["id"], reason=f"agregado manualmente via track_type.py ({term})")
    print(f"✔ {chosen['name']} (id={chosen['id']}) agregado a tracked_types.")


if __name__ == "__main__":
    main()
