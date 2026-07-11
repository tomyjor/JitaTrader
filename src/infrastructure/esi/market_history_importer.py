"""
Importador de market_history (volumen diario histórico) desde ESI.

Esta tabla existe en el schema desde el principio (database/schema.sql) y
LiquidityEngine/RiskEngine dependen de ella para el 40% de liquidez y 40%
del riesgo por liquidez -- pero hasta ahora NADA la poblaba. daily_volume
llegaba siempre en 0.0 al scoring, sin importar el item real, porque
get_daily_volume() lee de una tabla vacía. Este importador cierra ese hueco.

Endpoint: GET /markets/{region_id}/history/?type_id=X
Devuelve hasta ~1 año de historia diaria (date, average, highest, lowest,
volume, order_count). Guardamos todo lo que venga; get_daily_volume() ya
toma el más reciente (ORDER BY date DESC LIMIT 1).
"""

from datetime import datetime, timezone
from typing import List, Callable, Optional, Dict
import concurrent.futures as cf
import sqlite3
import threading

from infrastructure.esi.esi_client import ESIClient


class MarketHistoryImporter:
    def __init__(self, db_path: str = "database/trader.db"):
        self.db_path = db_path
        self.client = ESIClient()

    def import_type_history(self, region_id: int, type_id: int) -> int:
        """Importa la historia de un solo type_id. Devuelve cantidad de días insertados."""
        conn = sqlite3.connect(self.db_path)
        n = self._import_single(conn, region_id, type_id)
        conn.commit()
        conn.close()
        return n

    def import_bulk(
        self,
        region_id: int,
        type_ids: List[int],
        progress_callback: Optional[Callable[[int, int, int, Optional[str]], None]] = None,
        max_workers: int = 6,
    ) -> Dict:
        """
        Igual que MarketOrdersImporter.import_bulk: una sola conexión, un solo
        cliente HTTP con pooling, descarga concurrente (I/O-bound), escritura
        serializada con lock. Pensado para backfill de items ya trackeados
        que tienen order book pero nunca tuvieron historia importada.
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        write_lock = threading.Lock()
        total = len(type_ids)
        success = 0
        failed = []
        done = 0

        def fetch(type_id: int):
            try:
                history = self.client.get(f"/markets/{region_id}/history/", {"type_id": type_id})
                return type_id, history, None
            except Exception as e:
                return type_id, None, str(e)

        with cf.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch, tid): tid for tid in type_ids}
            for future in cf.as_completed(futures):
                type_id, history, error = future.result()
                if error is None:
                    try:
                        with write_lock:
                            self._write_history(conn, region_id, type_id, history)
                            conn.commit()
                        success += 1
                    except Exception as e:
                        error = str(e)
                        failed.append((type_id, error))
                else:
                    failed.append((type_id, error))

                done += 1
                if progress_callback:
                    progress_callback(done, total, type_id, error)

        conn.close()
        return {"success": success, "failed": failed}

    def _import_single(self, conn: sqlite3.Connection, region_id: int, type_id: int) -> int:
        try:
            history = self.client.get(f"/markets/{region_id}/history/", {"type_id": type_id})
        except Exception as e:
            print(f"  ✗ Error importando history de type_id {type_id}: {e}")
            return 0
        return self._write_history(conn, region_id, type_id, history)

    def _write_history(self, conn: sqlite3.Connection, region_id: int, type_id: int, history: list) -> int:
        n = 0
        for day in history:
            conn.execute("""
                INSERT OR REPLACE INTO market_history
                (region_id, type_id, date, average, highest, lowest, volume, order_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                region_id,
                type_id,
                day["date"],
                day.get("average"),
                day.get("highest"),
                day.get("lowest"),
                day.get("volume", 0),
                day.get("order_count", 0),
            ))
            n += 1
        return n

    def close(self):
        if hasattr(self, 'client') and self.client:
            self.client.close()
