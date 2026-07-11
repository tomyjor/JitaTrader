"""
Script para inicializar la base de datos trader.db con el schema.
Úsalo una sola vez (o cuando quieras resetear).

Uso:
    PYTHONPATH=src python scripts/setup_database.py
"""

import sys
from pathlib import Path
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / "database" / "trader.db"
SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"

def main():
    print(f"🗄️  Inicializando base de datos en {DB_PATH}...")
    
    if DB_PATH.exists():
        print("   La base ya existe. ¿Querés recrearla? (s/N)")
        if input().lower() != "s":
            print("Abortado.")
            return
        DB_PATH.unlink()

    DB_PATH.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    
    conn.executescript(schema)
    conn.commit()
    conn.close()
    
    print("✅ Tablas creadas correctamente.")
    print("   Ahora podés poblar item_types con el SDE si querés (o ya lo tenés).")
    print("   Usá track_type.py o la GUI para empezar a trackear productos.")

if __name__ == "__main__":
    main()
