"""
Diagnóstico de liquidez para los ítems trackeados.

Corré esto desde la raíz del proyecto:
    PYTHONPATH=src python scripts/diagnose_liquidity.py

Objetivo: separar dos causas MUY distintas que producen el mismo síntoma
("liquidez 0 en pantalla"):

  (A) Sesgo de muestreo: trackeaste ítems que genuinamente casi nunca se
      comercian en Jita (ver README / changelog Sprint 1 -- el bulk
      import "Panorama General" ordena por nombre alfabético, lo que
      concentra ítems narrativos/de facción con guiones simples al
      principio del nombre). Acá liquidez=0 es la lectura CORRECTA.

  (B) Un bug real: el ítem SÍ tiene volumen diario negociado
      (`daily_volume > 0`, evidencia de que se tradea) pero
      `total_sell_volume_remain` da 0 o casi 0 pese a que hay un sell
      price visible en pantalla -- eso sería inconsistente y merece
      revisión (ver la sección "SOSPECHOSOS" al final del output).

No inventa nada: si `market_history` está vacía para un ítem, este
script lo va a mostrar como `daily_volume=0.0` explícito, igual que hace
el resto del sistema.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infrastructure.repositories.sqlite_type_repository import SQLiteTypeRepository, JITA_REGION_ID
from infrastructure.repositories.sqlite_market_repository import SQLiteMarketRepository
from domain.services.liquidity_engine import LiquidityEngine, LiquidityInput


def main():
    db_path = Path(__file__).resolve().parent.parent / "database" / "trader.db"
    type_repo = SQLiteTypeRepository(db_path=db_path)
    market_repo = SQLiteMarketRepository(db_path=db_path)
    liquidity_engine = LiquidityEngine()

    tracked = type_repo.tracked_type_ids()
    if not tracked:
        print("No hay ítems trackeados todavía.")
        return

    print(f"Analizando {len(tracked)} ítem(s) trackeado(s)...\n")

    rows = []
    for tid in tracked:
        name = type_repo.get_name(tid) or f"Type-{tid}"
        daily_volume = market_repo.get_daily_volume(tid, JITA_REGION_ID)
        sell_remain = market_repo.total_sell_volume_remain(tid, JITA_REGION_ID)
        buy_remain = market_repo.total_buy_volume_remain(tid, JITA_REGION_ID)
        sell_count, buy_count = market_repo.order_counts(tid, JITA_REGION_ID)

        result = liquidity_engine.calculate(LiquidityInput(
            daily_volume=daily_volume,
            total_sell_volume_remain=sell_remain,
            sell_order_count=sell_count,
            buy_order_count=buy_count,
        ))
        liq = result.value

        rows.append({
            "id": tid,
            "name": name,
            "daily_volume": daily_volume,
            "sell_remain": sell_remain,
            "buy_remain": buy_remain,
            "sell_count": sell_count,
            "buy_count": buy_count,
            "liquidity_score": liq.liquidity_score,
            "depth_score": liq.depth_score,
        })

    # === Resumen agregado ===
    no_history = [r for r in rows if r["daily_volume"] == 0]
    has_history_but_zero_depth = [
        r for r in rows if r["daily_volume"] > 0 and r["sell_remain"] == 0
    ]
    genuinely_liquid = [r for r in rows if r["liquidity_score"] >= 15]

    print("=" * 78)
    print("RESUMEN")
    print("=" * 78)
    print(f"Total trackeados evaluados:                         {len(rows)}")
    print(f"Sin NINGÚN día de historial de volumen (daily_volume=0):  {len(no_history)}  "
          f"({100*len(no_history)/len(rows):.0f}%)")
    print(f"Con historial de volumen PERO 0 unidades en venta hoy:    {len(has_history_but_zero_depth)}  "
          f"({100*len(has_history_but_zero_depth)/len(rows):.0f}%)")
    print(f"Con liquidez real (score >= 15):                          {len(genuinely_liquid)}  "
          f"({100*len(genuinely_liquid)/len(rows):.0f}%)")
    print()

    if len(no_history) == len(rows):
        print("⚠️  El 100% no tiene NINGÚN día de historial de volumen importado.")
        print("    Antes de sacar conclusiones sobre el motor de liquidez, corré:")
        print("    Dashboard → sidebar → '📈 Importar volumen histórico (fix liquidez/score)'")
        print("    y volvé a correr este diagnóstico.")
        print()
    elif len(no_history) / len(rows) > 0.5:
        print(f"ℹ️  Más de la mitad ({len(no_history)}/{len(rows)}) no tiene historial de volumen.")
        print("    Si trackeaste con 'Panorama General', puede ser sesgo de muestreo")
        print("    (ver mensaje en el chat) más que falta de importación -- revisá los")
        print("    nombres de esos ítems abajo: si son variantes narrativas/de facción")
        print("    ('X' Something), es esperable que Jita nunca les tenga historial real.")
        print()

    # === Sospechosos reales: tienen volumen diario pero profundidad en 0 ===
    if has_history_but_zero_depth:
        print("=" * 78)
        print(f"SOSPECHOSOS ({len(has_history_but_zero_depth)}): tienen volumen diario real")
        print("pero CERO unidades en venta ahora mismo. Puede ser normal (el book se")
        print("vació desde el último snapshot), pero si aparecen muchos vale la pena")
        print("revisar si el import de market_orders está corriendo bien para estos IDs.")
        print("=" * 78)
        for r in has_history_but_zero_depth[:20]:
            print(f"  {r['name'][:45]:<45} ID={r['id']:<8} daily_volume={r['daily_volume']:.1f}  "
                  f"sell_orders={r['sell_count']}  buy_orders={r['buy_count']}")
        if len(has_history_but_zero_depth) > 20:
            print(f"  ... y {len(has_history_but_zero_depth) - 20} más.")
        print()

    # === Top 15 por liquidez real, para ver si HAY algo bueno ===
    top_liquid = sorted(rows, key=lambda r: -r["liquidity_score"])[:15]
    print("=" * 78)
    print("TOP 15 POR LIQUIDEZ REAL (para confirmar que el motor SÍ distingue)")
    print("=" * 78)
    print(f"{'Item':<40}{'Liq.Score':>10}{'DailyVol':>12}{'SellRemain':>14}")
    for r in top_liquid:
        print(f"{r['name'][:38]:<40}{r['liquidity_score']:>10.1f}{r['daily_volume']:>12.1f}{r['sell_remain']:>14.0f}")

    print()
    print("Si el TOP 15 tiene scores todos en 0.0 también, hay algo más raro y")
    print("conviene pegar este output completo para seguir investigando.")


if __name__ == "__main__":
    main()
