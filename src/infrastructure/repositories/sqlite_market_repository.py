"""
Infrastructure: SQLiteMarketRepository
Implementación real del port MarketRepository, contra
database/trader.db (tablas market_orders y market_history, pobladas por
el importador de ESI).

Decisión de diseño deliberada: si no hay órdenes o historia para un
type_id/region_id, los métodos devuelven None / 0.0 explícitamente, NUNCA
un valor por defecto inventado (el use case anterior hacía
`item.get("daily_volume", 50000)` -- eso es exactamente el tipo de dato
fabricado que el RFC-000 prohíbe). Es responsabilidad del caller decidir
qué hacer con la ausencia de evidencia (típicamente: excluir el ítem del
análisis, no fingar que tiene volumen).
"""

import sqlite3
from pathlib import Path
from typing import Optional

from domain.ports.market_repository import MarketRepository, MarketSnapshot
from domain.value_objects.money import Money

DEFAULT_DB_PATH = Path("database/trader.db")


class SQLiteMarketRepository(MarketRepository):

    #: Cantidad de días recientes de market_history sobre los que se
    #: promedia get_daily_volume(). v1.1: antes se usaba solo el día más
    #: reciente, una muestra ruidosa -- un solo día atípicamente alto o
    #: bajo distorsionaba directamente el score de liquidez del ítem
    #: (ver LiquidityEngine v1.4). Promediar una ventana da una lectura
    #: más estable sin dejar de ser honesto: si hay menos de N días de
    #: historia, se promedia sobre los que haya; si no hay ninguno, se
    #: sigue devolviendo 0.0 explícito.
    DAILY_VOLUME_WINDOW_DAYS = 7

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_current_snapshot(self, type_id: int, region_id: int) -> Optional[MarketSnapshot]:
        conn = self._connect()
        best_sell = conn.execute(
            "SELECT MIN(price) AS p FROM market_orders "
            "WHERE type_id=? AND region_id=? AND is_buy_order=0",
            (type_id, region_id),
        ).fetchone()["p"]
        best_buy = conn.execute(
            "SELECT MAX(price) AS p FROM market_orders "
            "WHERE type_id=? AND region_id=? AND is_buy_order=1",
            (type_id, region_id),
        ).fetchone()["p"]
        conn.close()

        # Sin las dos puntas del order book no hay spread real -- no
        # inventamos una de las dos, devolvemos None y que el caller decida.
        if best_sell is None or best_buy is None:
            return None

        daily_volume = self.get_daily_volume(type_id, region_id)

        return MarketSnapshot(
            type_id=type_id,
            buy_price=Money(int(best_buy * 100)),
            sell_price=Money(int(best_sell * 100)),
            daily_volume=daily_volume,
        )

    def get_daily_volume(self, type_id: int, region_id: int) -> float:
        """
        Volumen diario "representativo" para liquidez, promediado sobre
        los últimos `DAILY_VOLUME_WINDOW_DAYS` días disponibles de
        market_history (ver docstring de la constante). 0.0 explícito si
        no hay ningún día de historia -- "no hay evidencia de volumen
        reciente", nunca "asumimos un volumen típico".
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT volume FROM market_history "
            "WHERE type_id=? AND region_id=? ORDER BY date DESC LIMIT ?",
            (type_id, region_id, self.DAILY_VOLUME_WINDOW_DAYS),
        ).fetchall()
        conn.close()

        volumes = [r["volume"] for r in rows if r["volume"] is not None]
        if not volumes:
            return 0.0
        return sum(volumes) / len(volumes)

    def order_counts(self, type_id: int, region_id: int) -> tuple[int, int]:
        """(sell_order_count, buy_order_count). Método de infraestructura,
        no forma parte del port abstracto -- lo necesita el use case para
        alimentar CompetitionEngine."""
        conn = self._connect()
        sell_count = conn.execute(
            "SELECT COUNT(*) AS n FROM market_orders WHERE type_id=? AND region_id=? AND is_buy_order=0",
            (type_id, region_id),
        ).fetchone()["n"]
        buy_count = conn.execute(
            "SELECT COUNT(*) AS n FROM market_orders WHERE type_id=? AND region_id=? AND is_buy_order=1",
            (type_id, region_id),
        ).fetchone()["n"]
        conn.close()
        return sell_count, buy_count

    def total_sell_volume_remain(self, type_id: int, region_id: int) -> float:
        """Suma de volume_remain de las órdenes de VENTA activas."""
        conn = self._connect()
        row = conn.execute(
            "SELECT COALESCE(SUM(volume_remain), 0) AS v FROM market_orders "
            "WHERE type_id=? AND region_id=? AND is_buy_order=0",
            (type_id, region_id),
        ).fetchone()
        conn.close()
        return float(row["v"])

    def total_buy_volume_remain(self, type_id: int, region_id: int) -> float:
        """
        Suma de volume_remain de las órdenes de COMPRA activas.

        Análogo a total_sell_volume_remain. Necesario para que
        CompetitionEngine reciba un `total_buy_volume` real -- antes
        OpportunityEngine lo pasaba hardcodeado en 0.0, lo que dejaba a
        `market_density` ciego a la mitad del order book.
        """
        conn = self._connect()
        row = conn.execute(
            "SELECT COALESCE(SUM(volume_remain), 0) AS v FROM market_orders "
            "WHERE type_id=? AND region_id=? AND is_buy_order=1",
            (type_id, region_id),
        ).fetchone()
        conn.close()
        return float(row["v"])
