#!/usr/bin/env python3
"""
Importa categorías y grupos reales del SDE de EVE Online (archivos JSONL).

Uso:
    python scripts/import_sde_categories_groups.py /ruta/a/carpeta_con_los_jsonl

El script busca automáticamente:
    - invCategories.jsonl  o  categories.jsonl
    - invGroups.jsonl      o  groups.jsonl

Luego popula las tablas 'categories' y 'groups' en trader.db
"""

import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional


def find_jsonl_file(base_dir: Path, possible_names: list[str]) -> Optional[Path]:
    for name in possible_names:
        p = base_dir / name
        if p.exists():
            return p
    # Búsqueda recursiva
    for name in possible_names:
        matches = list(base_dir.rglob(name))
        if matches:
            return matches[0]
    return None


def import_categories(conn: sqlite3.Connection, jsonl_path: Path):
    print(f"Importando categorías desde: {jsonl_path}")
    count = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                cat_id = obj.get("_key") or obj.get("id") or obj.get("categoryID")
                name = obj.get("name", {}).get("en") if isinstance(obj.get("name"), dict) else obj.get("name")
                published = obj.get("published", 1)

                if cat_id and name:
                    conn.execute(
                        "INSERT OR REPLACE INTO categories (id, name, published) VALUES (?, ?, ?)",
                        (int(cat_id), str(name), int(published))
                    )
                    count += 1
            except Exception as e:
                print(f"  Error en línea: {e}")
    conn.commit()
    print(f"  → {count} categorías importadas/actualizadas.")


def import_groups(conn: sqlite3.Connection, jsonl_path: Path):
    print(f"Importando grupos desde: {jsonl_path}")
    count = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                grp_id = obj.get("_key") or obj.get("id") or obj.get("groupID")
                cat_id = obj.get("categoryID") or obj.get("category_id")
                name = obj.get("name", {}).get("en") if isinstance(obj.get("name"), dict) else obj.get("name")
                published = obj.get("published", 1)

                if grp_id and cat_id and name:
                    conn.execute(
                        """INSERT OR REPLACE INTO groups (id, category_id, name, published)
                           VALUES (?, ?, ?, ?)""",
                        (int(grp_id), int(cat_id), str(name), int(published))
                    )
                    count += 1
            except Exception as e:
                print(f"  Error en línea: {e}")
    conn.commit()
    print(f"  → {count} grupos importados/actualizados.")


def main():
    project_root = Path(__file__).resolve().parents[1]
    default_sde_dir = project_root / "sde"

    if len(sys.argv) > 1:
        base_dir = Path(sys.argv[1]).expanduser().resolve()
    else:
        base_dir = default_sde_dir
        print(f"📁 Usando carpeta SDE por defecto del proyecto: {base_dir}")

    if not base_dir.exists():
        print(f"ERROR: La carpeta SDE no existe: {base_dir}")
        print("Asegurate de tener 'sde/categories.jsonl' y 'sde/groups.jsonl' dentro de la carpeta 'sde/' del proyecto.")
        sys.exit(1)

    # Buscar archivos (prioriza los nombres que usás)
    cat_file = find_jsonl_file(base_dir, ["categories.jsonl", "invCategories.jsonl"])
    grp_file = find_jsonl_file(base_dir, ["groups.jsonl", "invGroups.jsonl"])

    if not cat_file:
        print("ERROR: No se encontró categories.jsonl ni invCategories.jsonl")
        sys.exit(1)
    if not grp_file:
        print("ERROR: No se encontró groups.jsonl ni invGroups.jsonl")
        sys.exit(1)

    db_path = Path(__file__).resolve().parents[1] / "database" / "trader.db"
    print(f"Base de datos: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    import_categories(conn, cat_file)
    import_groups(conn, grp_file)

    conn.close()
    print("\n✅ Importación de categorías y grupos completada.")
    print("Ahora el explorador de la GUI debería mostrar nombres reales de EVE.")


if __name__ == "__main__":
    main()
