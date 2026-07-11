"""
Infrastructure: SQLiteTypeRepository
Implementación real del port TypeRepository, contra database/trader.db
(la base que ya tenés poblada con 52,744 types del SDE de CCP).
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timezone

from domain.ports.type_repository import TypeRepository

DEFAULT_DB_PATH = Path("database/trader.db")
JITA_REGION_ID = 10000002


class SQLiteTypeRepository(TypeRepository):

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_exists(self, table_name: str) -> bool:
        """Verifica si una tabla existe en la base de datos (para queries defensivas)."""
        conn = self._connect()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        conn.close()
        return row is not None

    def get(self, type_id: int) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT id, name, group_id, category_id, market_group_id, "
            "volume, base_price, published FROM item_types WHERE id=?",
            (type_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_name(self, type_id: int) -> Optional[str]:
        item = self.get(type_id)
        return item["name"] if item else None

    def search(self, term: str, limit: int = 20) -> List[Dict]:
        """
        No es parte del port abstracto (el dominio no necesita "buscar",
        solo "obtener por id"), pero es un método de infraestructura
        práctico para poblar tracked_types desde un nombre en vez de un id
        a mano. Ver scripts/track_type.py y la GUI.
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, name FROM item_types "
            "WHERE name LIKE ? AND published = 1 ORDER BY name LIMIT ?",
            (f"%{term.strip()}%", limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def tracked_type_ids(self) -> List[int]:
        conn = self._connect()
        rows = conn.execute("SELECT type_id FROM tracked_types").fetchall()
        conn.close()
        return [r["type_id"] for r in rows]

    def track(self, type_id: int, reason: str | None = None) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT OR IGNORE INTO tracked_types (type_id, added_at, reason) VALUES (?, ?, ?)",
            (type_id, datetime.now(timezone.utc).isoformat(), reason),
        )
        conn.commit()
        conn.close()

    def untrack(self, type_id: int, also_cleanup_orders: bool = True) -> None:
        """
        Elimina un type_id de tracked_types.
        Si also_cleanup_orders=True (default), también borra su snapshot de market_orders
        en Jita para mantener la DB limpia (evita órdenes obsoletas de items que ya no seguimos).
        """
        conn = self._connect()
        conn.execute("DELETE FROM tracked_types WHERE type_id = ?", (type_id,))

        if also_cleanup_orders:
            conn.execute(
                "DELETE FROM market_orders WHERE type_id = ? AND region_id = ?",
                (type_id, JITA_REGION_ID)
            )
            # Nota: No borramos market_history porque es histórico acumulativo y útil para trends.
            # Si se quiere cleanup completo, se puede agregar después.

        conn.commit()
        conn.close()

    def is_tracked(self, type_id: int) -> bool:
        conn = self._connect()
        row = conn.execute(
            "SELECT 1 FROM tracked_types WHERE type_id = ?",
            (type_id,)
        ).fetchone()
        conn.close()
        return row is not None

    # ============================================================
    # NUEVOS MÉTODOS PARA NAVEGACIÓN POR CATEGORÍA / GRUPO (EVE SDE)
    # ============================================================

    def get_distinct_categories(self) -> List[Dict]:
        """Devuelve TODAS las categorías con items publicados.
        Usa nombres reales de la tabla 'categories' si existe, sino usa nombre de item como fallback."""
        conn = self._connect()

        if self._table_exists("categories"):
            query = """
                SELECT 
                    it.category_id,
                    COUNT(*) as item_count,
                    COALESCE(cat.name, 
                        (SELECT name FROM item_types i2 
                         WHERE i2.category_id = it.category_id AND i2.published=1 
                         ORDER BY LENGTH(i2.name) ASC LIMIT 1)
                    ) as name
                FROM item_types it
                LEFT JOIN categories cat ON cat.id = it.category_id
                WHERE it.published = 1 AND it.category_id IS NOT NULL
                GROUP BY it.category_id
                ORDER BY it.category_id ASC
            """
        else:
            # Fallback seguro si todavía no se importó el SDE
            query = """
                SELECT 
                    category_id,
                    COUNT(*) as item_count,
                    MIN(name) as name
                FROM item_types
                WHERE published = 1 AND category_id IS NOT NULL
                GROUP BY category_id
                ORDER BY category_id ASC
            """

        rows = conn.execute(query).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_groups_by_category(self, category_id: int) -> List[Dict]:
        """Grupos dentro de una categoría. Usa nombres reales si la tabla 'groups' existe."""
        conn = self._connect()

        if self._table_exists("groups"):
            query = """
                SELECT 
                    it.group_id,
                    COUNT(*) as item_count,
                    COALESCE(grp.name,
                        (SELECT name FROM item_types i2 
                         WHERE i2.group_id = it.group_id AND i2.published=1 
                         ORDER BY LENGTH(i2.name) ASC LIMIT 1)
                    ) as name
                FROM item_types it
                LEFT JOIN groups grp ON grp.id = it.group_id
                WHERE it.published = 1 AND it.category_id = ?
                GROUP BY it.group_id
                ORDER BY it.group_id ASC
            """
            params = (category_id,)
        else:
            query = """
                SELECT 
                    group_id,
                    COUNT(*) as item_count,
                    MIN(name) as name
                FROM item_types
                WHERE published = 1 AND category_id = ?
                GROUP BY group_id
                ORDER BY group_id ASC
            """
            params = (category_id,)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_types_in_group(self, group_id: int, limit: int = 40) -> List[Dict]:
        """Items de un grupo específico (útil para mostrar en UI y trackear)."""
        conn = self._connect()
        rows = conn.execute("""
            SELECT id, name, volume, base_price
            FROM item_types
            WHERE group_id = ? AND published = 1
            ORDER BY name
            LIMIT ?
        """, (group_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_category_name(self, category_id: int) -> str:
        """Nombre representativo de categoría (usando un item como proxy)."""
        conn = self._connect()
        row = conn.execute(
            "SELECT name FROM item_types WHERE category_id = ? AND published=1 LIMIT 1",
            (category_id,)
        ).fetchone()
        conn.close()
        return row["name"] if row else f"Category {category_id}"
