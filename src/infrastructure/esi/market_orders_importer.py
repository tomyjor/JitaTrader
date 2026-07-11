"""
Importador de market_orders (order book actual) desde ESI.
Soporta import por región completa, por type_id individual (para auto-import en GUI),
o en bulk concurrente (para cargas masivas de 100-400 items desde la GUI).
"""

from datetime import datetime, timezone
from typing import List, Callable, Optional, Dict
import concurrent.futures as cf
import sqlite3
import threading

from infrastructure.esi.esi_client import ESIClient


class MarketOrdersImporter:
    def __init__(self, db_path: str = "database/trader.db"):
        self.db_path = db_path
        self.client = ESIClient()

    def import_region_orders(self, region_id: int, type_ids: List[int]):
        """Importa órdenes para múltiples types en una región (borra TODO el order book de la región primero)."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM market_orders WHERE region_id = ?", (region_id,))

        for type_id in type_ids:
            self._import_single_type(conn, region_id, type_id)

        conn.commit()
        conn.close()
        self.client.close()

    def import_type_orders(self, region_id: int, type_id: int):
        """
        Importa/reemplaza el order book SOLO para un type_id específico en la región.
        Ideal para llamado automático desde la GUI al trackear un item.
        Borra solo las órdenes viejas de ese type_id antes de insertar las nuevas.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "DELETE FROM market_orders WHERE region_id = ? AND type_id = ?",
            (region_id, type_id)
        )

        self._import_single_type(conn, region_id, type_id)

        conn.commit()
        conn.close()
        # No cerramos el client aquí para reutilizar si se llama múltiples veces,
        # pero para simplicidad en GUI lo recreamos o manejamos afuera.
        # Por ahora, como es por item, cerramos.
        self.client.close()

    def _import_single_type(self, conn: sqlite3.Connection, region_id: int, type_id: int):
        """Helper: descarga e inserta las órdenes de un solo type."""
        try:
            orders = self.client.get(f"/markets/{region_id}/orders/", {
                "type_id": type_id
            })

            fetched_at = datetime.now(timezone.utc).isoformat()

            for order in orders:
                conn.execute("""
                    INSERT OR REPLACE INTO market_orders 
                    (order_id, region_id, type_id, is_buy_order, price, 
                     volume_remain, volume_total, min_volume, duration, 
                     issued, location_id, order_range, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order["order_id"],
                    region_id,
                    type_id,
                    1 if order["is_buy_order"] else 0,
                    order["price"],
                    order["volume_remain"],
                    order["volume_total"],
                    order.get("min_volume", 1),
                    order["duration"],
                    order["issued"],
                    order["location_id"],
                    order.get("range", ""),
                    fetched_at
                ))

            print(f"  ✓ Type {type_id}: {len(orders)} órdenes importadas")
        except Exception as e:
            print(f"  ✗ Error importando type_id {type_id}: {e}")
            # No re-raise para que la GUI pueda continuar y mostrar error amigable

    def import_bulk(
        self,
        region_id: int,
        type_ids: List[int],
        progress_callback: Optional[Callable[[int, int, int, Optional[str]], None]] = None,
        max_workers: int = 6,
    ) -> Dict:
        """
        Import masivo eficiente para 100-400+ type_ids.

        A diferencia de llamar import_type_orders() en loop (lo que hacía la GUI antes),
        esto:
        - Reutiliza UNA sola sesión HTTP (self.client) con connection pooling, en vez de
          crear un ESIClient nuevo por item.
        - Descarga las órdenes de ESI en paralelo con un pool de threads (I/O-bound, así
          que el paralelismo ayuda de verdad acá — la CPU no es el cuello de botella).
        - Escribe a SQLite serializado en un solo hilo (sqlite3 no es thread-safe para
          escrituras concurrentes sobre la misma conexión), así que las escrituras van
          por una cola simple protegida con un lock.

        progress_callback(done, total, type_id, error) se llama después de cada item
        (exitoso o no) para que la GUI pueda actualizar una barra de progreso en vivo.

        Devuelve {"success": int, "failed": [(type_id, error), ...]}.
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        write_lock = threading.Lock()
        total = len(type_ids)
        success = 0
        failed = []
        done = 0

        def fetch(type_id: int):
            try:
                orders = self.client.get(f"/markets/{region_id}/orders/", {"type_id": type_id})
                return type_id, orders, None
            except Exception as e:
                return type_id, None, str(e)

        def write(type_id: int, orders: list):
            fetched_at = datetime.now(timezone.utc).isoformat()
            with write_lock:
                conn.execute(
                    "DELETE FROM market_orders WHERE region_id = ? AND type_id = ?",
                    (region_id, type_id)
                )
                for order in orders:
                    conn.execute("""
                        INSERT OR REPLACE INTO market_orders
                        (order_id, region_id, type_id, is_buy_order, price,
                         volume_remain, volume_total, min_volume, duration,
                         issued, location_id, order_range, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        order["order_id"],
                        region_id,
                        type_id,
                        1 if order["is_buy_order"] else 0,
                        order["price"],
                        order["volume_remain"],
                        order["volume_total"],
                        order.get("min_volume", 1),
                        order["duration"],
                        order["issued"],
                        order["location_id"],
                        order.get("range", ""),
                        fetched_at
                    ))
                conn.commit()

        with cf.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch, tid): tid for tid in type_ids}
            for future in cf.as_completed(futures):
                type_id, orders, error = future.result()
                if error is None:
                    try:
                        write(type_id, orders)
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

    def close(self):
        if hasattr(self, 'client') and self.client:
            self.client.close()
