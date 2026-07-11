import sys
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone


def _find_project_root(start: Path) -> Path:
    """
    Ver docstring gemela en app.py. Corrige un bug real: este archivo
    vive un nivel más profundo que app.py (dentro de `pages/`), así que
    el índice `parents[3]` que tenía antes (copiado de app.py) apuntaba
    a una ruta inexistente (`.../src/src`). Pasaba inadvertido porque
    Streamlit corre todas las páginas en el mismo proceso, y ya había
    quedado el path correcto en sys.path desde que se cargó app.py
    primero -- pero cualquier ejecución que no pasara antes por app.py
    hubiera roto todos los imports acá abajo.
    """
    current = start
    while not (current / "src").exists() and current.parent != current:
        current = current.parent
    return current


sys.path.insert(0, str(_find_project_root(Path(__file__).resolve()) / "src"))

import streamlit as st
from infrastructure.repositories.sqlite_type_repository import SQLiteTypeRepository, JITA_REGION_ID
from infrastructure.repositories.sqlite_market_repository import SQLiteMarketRepository
from infrastructure.esi.market_orders_importer import MarketOrdersImporter
from infrastructure.esi.market_history_importer import MarketHistoryImporter
from application.use_cases.detect_opportunities_use_case import (
    DetectOpportunitiesUseCase, DetectOpportunitiesRequest
)
from domain.services.opportunity_engine import OpportunityEngine
from domain.value_objects.tax_profile import TaxProfile
from presentation.streamlit_app.components.opportunity_table import (
    render_recommendation_badge, render_score_breakdown, show_opportunity_table
)

st.set_page_config(page_title="Tracked Items - JitaTrader v2", layout="wide")
st.title("📋 Gestión de Productos Trackeados")

type_repo = SQLiteTypeRepository()
market_repo = SQLiteMarketRepository()
opportunity_engine = OpportunityEngine()
use_case = DetectOpportunitiesUseCase(market_repo, type_repo, opportunity_engine)
tax_profile = TaxProfile(broker_fee_rate=0.03, sales_tax_rate=0.036)

tracked_ids = type_repo.tracked_type_ids()

# ============================================================
# PESTAÑAS PRINCIPALES
# ============================================================
tab_tracked, tab_search = st.tabs(["📋 Tracked Items (Mis seleccionados)", "🔍 Buscar y Agregar"])

# ============================================================
# TAB 1: TRACKED ITEMS - Lista limpia de seleccionados
# ============================================================
with tab_tracked:
    st.subheader("Productos que estás trackeando actualmente")

    # === BOTÓN BULK DELETE ===
    if tracked_ids:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"Tienes **{len(tracked_ids)}** productos en tu watchlist.")
        with col2:
            if st.button("🗑️ Eliminar TODOS los trackeados", type="secondary"):
                if st.session_state.get("confirm_delete_all", False):
                    errors = []
                    for tid in tracked_ids:
                        try:
                            type_repo.untrack(tid, also_cleanup_orders=True)
                        except Exception as e:
                            errors.append((tid, str(e)))
                    ok_count = len(tracked_ids) - len(errors)
                    if errors:
                        st.warning(f"Se eliminaron {ok_count} de {len(tracked_ids)}. {len(errors)} fallaron:")
                        for tid, err in errors[:5]:
                            st.caption(f"• ID {tid}: {err}")
                    else:
                        st.success(f"✅ Se eliminaron {ok_count} productos.")
                    st.session_state["confirm_delete_all"] = False
                    st.rerun()
                else:
                    st.session_state["confirm_delete_all"] = True
                    st.warning("⚠️ ¿Estás seguro? Esta acción no se puede deshacer. Presioná el botón nuevamente para confirmar.")

    if tracked_ids:
        # Opciones de filtrado rápido
        show_only_without_data = st.checkbox("Mostrar solo los que NO tienen datos importados", value=False)

        items_to_show = []
        for tid in tracked_ids:
            name = type_repo.get_name(tid) or f"Type-{tid}"
            has_orders = False
            try:
                conn = type_repo._connect()
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM market_orders WHERE type_id=? AND region_id=?",
                    (tid, JITA_REGION_ID)
                ).fetchone()
                conn.close()
                has_orders = row["c"] > 0 if row else False
            except sqlite3.Error as e:
                # Antes esto era un `except: pass` que ocultaba cualquier
                # error de DB en silencio. Un fallo acá probablemente
                # significa una base corrupta o un schema desactualizado
                # -- vale la pena que el usuario lo vea en vez de que el
                # ítem aparezca silenciosamente como "sin datos".
                st.caption(f"⚠️ No se pudo verificar datos de **{name}** (ID {tid}): {e}")

            if show_only_without_data and has_orders:
                continue

            items_to_show.append({
                "id": tid,
                "name": name,
                "has_data": has_orders
            })

        # Pre-calculamos score y recomendación para los ítems con datos,
        # reutilizando el MISMO use case que usa el Dashboard (una sola
        # pasada para todos, no un motor por fila) para poder mostrar el
        # desglose acá también sin duplicar la orquestación de motores.
        ids_with_data = [item["id"] for item in items_to_show if item["has_data"]]
        opportunities_by_id = {}
        if ids_with_data:
            calc_request = DetectOpportunitiesRequest(
                type_ids=ids_with_data, region_id=JITA_REGION_ID, tax_profile=tax_profile
            )
            calc_result = use_case.execute(calc_request, min_score=0, max_results=len(ids_with_data))
            opportunities_by_id = {r.value.type_id: r for r in calc_result.ranked_all}

        if items_to_show:
            st.caption(f"Mostrando {len(items_to_show)} de {len(tracked_ids)} productos trackeados.")

            # Con watchlists grandes (p.ej. 400 ítems de un import masivo),
            # renderizar un checkbox + caption + badge + expander POR CADA
            # fila es pesado para el navegador. Se ofrece una vista de
            # tabla rápida y ordenable por columna (click en el header,
            # nativo de st.dataframe) como alternativa; para watchlists
            # chicas se sigue arrancando en modo Gestión por default.
            default_view = "📊 Tabla resumen (ordenable, rápida)" if len(items_to_show) > 50 else "✅ Gestión (marcar / quitar)"
            view_mode = st.radio(
                "Vista",
                ["✅ Gestión (marcar / quitar)", "📊 Tabla resumen (ordenable, rápida)"],
                index=0 if default_view.startswith("✅") else 1,
                horizontal=True,
                label_visibility="collapsed",
                key="tracked_view_mode",
            )

            if view_mode.startswith("📊"):
                table_opportunities = list(opportunities_by_id.values())
                if table_opportunities:
                    show_opportunity_table(table_opportunities)
                    st.caption(
                        "💡 Click en el header de cualquier columna (Score, ROI %, Liquidez, etc.) "
                        "para ordenar. Los ítems sin order book importado no tienen score y no "
                        "aparecen acá -- usá la vista de Gestión para verlos."
                    )
                else:
                    st.info("Ninguno de los ítems mostrados tiene datos de mercado importados todavía.")

            else:
                # Usamos checkboxes para selección múltiple
                selected_to_remove = []
                for item in items_to_show:
                    col1, col2, col3 = st.columns([6, 2.5, 1.5])
                    with col1:
                        label = f"**{item['name']}** (ID: {item['id']})"
                        checked = st.checkbox(label, value=True, key=f"track_{item['id']}")
                        if not checked:
                            selected_to_remove.append(item['id'])

                        opp_result = opportunities_by_id.get(item['id'])
                        if opp_result:
                            o = opp_result.value
                            st.caption(
                                f"📊 Score **{o.score:.1f}** · ROI {o.roi_percent:.1f}% · "
                                f"Riesgo {o.risk.risk_level} · Liquidez {o.liquidity.liquidity_score:.0f}/100"
                            )
                            render_recommendation_badge(o)
                            with st.expander("🔍 Ver desglose del score"):
                                render_score_breakdown(o.score_breakdown)

                    with col2:
                        status = "✅ Datos importados" if item['has_data'] else "⏳ Sin datos de order book"
                        st.caption(status)

                    with col3:
                        if st.button("🗑️ Quitar", key=f"quick_untrack_{item['id']}"):
                            type_repo.untrack(item['id'], also_cleanup_orders=True)
                            st.success(f"✅ {item['name']} quitado.")
                            st.rerun()

                # Botón para quitar múltiples
                if selected_to_remove:
                    if st.button(f"🗑️ Quitar los {len(selected_to_remove)} seleccionados", type="primary"):
                        for tid in selected_to_remove:
                            type_repo.untrack(tid, also_cleanup_orders=True)
                        st.success(f"✅ {len(selected_to_remove)} productos quitados de la watchlist.")
                        st.rerun()
        else:
            st.info("No hay productos que cumplan el filtro actual.")
    else:
        st.info("Aún no tenés productos trackeados. Usá la pestaña **Buscar y Agregar** para empezar.")

# ============================================================
# TAB 2: BUSCAR Y AGREGAR (todas las herramientas de búsqueda)
# ============================================================
with tab_search:
    st.subheader("🔍 Buscar y Agregar productos (importación automática)")

    # --- BÚSQUEDA LIBRE ---
    st.markdown("### Búsqueda libre por nombre")
    search_term = st.text_input(
        "Escribí cualquier parte del nombre",
        key="search_in_tab",
        placeholder="Ej: Scourge, Shield, Warp Disruptor, Tritanium..."
    )

    if search_term:
        results = type_repo.search(search_term.strip(), limit=12)
        if results:
            for item in results:
                col1, col2 = st.columns([5.5, 2.5])
                with col1:
                    st.write(f"**{item['name']}** (ID: {item['id']})")
                with col2:
                    if type_repo.is_tracked(item['id']):
                        st.success("✅ Ya trackeado")
                    else:
                        if st.button("🚀 Trackear + Importar", key=f"search_track_{item['id']}", type="primary"):
                            with st.spinner(f"Importando {item['name']}..."):
                                type_repo.track(item['id'], reason=f"Búsqueda: {search_term}")
                                importer = MarketOrdersImporter()
                                importer.import_type_orders(JITA_REGION_ID, item['id'])
                                importer.close()
                                hist_importer = MarketHistoryImporter()
                                hist_importer.import_type_history(JITA_REGION_ID, item['id'])
                                hist_importer.close()
                            st.success(f"✅ {item['name']} agregado e importado (órdenes + historial de volumen).")
                            st.rerun()
        else:
            st.info("No se encontraron resultados.")

    st.divider()

    # ============================================================
    # BOTÓN PANORAMA GENERAL - MUESTRA DE ITEMS (ONE-CLICK BULK)
    # Fuera de un expander colapsado a propósito: es la acción más importante
    # de esta pestaña para poblar Discovery, así que va visible y arriba.
    #
    # v1.1: el título decía "TODOS los items", pero el SDE tiene ~27.000
    # ítems publicados y esto siempre trajo como mucho unos cientos -- es
    # una MUESTRA, no el universo. Corregido el texto para no generar la
    # falsa impresión de estar viendo "todo el mercado".
    # ============================================================
    st.markdown("### 🌍 Cargar una muestra de items (Panorama General / Discovery)")
    st.caption(
        "Tu SDE tiene ~27.000 ítems publicados en total. Esto trackea una MUESTRA "
        "aleatoria de hasta el número que elijas abajo, no el universo completo."
    )

    bulk_col1, bulk_col2 = st.columns([2, 1])
    with bulk_col1:
        bulk_limit = st.slider(
            "Cantidad de items a trackear + importar", 100, 2000, 300, step=50,
            key="bulk_limit_slider"
        )
    with bulk_col2:
        # x2 porque además del import de órdenes se corre el de historial
        # de volumen inmediatamente después (ver más abajo) -- la
        # estimación vieja solo contaba la primera pasada y subestimaba
        # el tiempo real a la mitad.
        est_minutes = max(1, round(bulk_limit / 6 * 0.6 / 60 * 2, 1))
        st.metric("Tiempo estimado", f"~{est_minutes} min")

    st.warning(
        f"⚠️ Esto trackeará e importará automáticamente una muestra ALEATORIA de hasta "
        f"**{bulk_limit}** items publicados (descarga concurrente contra ESI, 6 workers en "
        "paralelo, órdenes + historial de volumen). Puede tardar varios minutos según la "
        "cantidad y la latencia de ESI."
    )
    st.caption(
        "💡 Es aleatoria a propósito: ordenar por nombre concentraba la muestra en variantes "
        "narrativas/de facción (ítems que empiezan con comilla, ej. 'Basic' X) que casi nunca "
        "se comercian en Jita -- eso hacía parecer que 'todo tiene liquidez 0' cuando en "
        "realidad era la muestra la que estaba sesgada, no el cálculo de liquidez."
    )

    if st.button(f"🚀 Trackear + Importar muestra de items (hasta {bulk_limit})", type="primary", use_container_width=True):
        try:
            conn = type_repo._connect()
            rows = conn.execute("""
                SELECT id, name
                FROM item_types
                WHERE published = 1
                ORDER BY RANDOM()
                LIMIT ?
            """, (bulk_limit,)).fetchall()

            if not rows:
                conn.close()
                st.info("No se encontraron items publicados.")
            else:
                all_ids = [r["id"] for r in rows]
                names_by_id = {r["id"]: r["name"] for r in rows}

                # Chequeo bulk de ya-trackeados en UNA query en vez de una por item
                placeholders = ",".join("?" * len(all_ids))
                already_tracked_ids = {
                    r["type_id"] for r in conn.execute(
                        f"SELECT type_id FROM tracked_types WHERE type_id IN ({placeholders})",
                        all_ids
                    ).fetchall()
                }
                new_ids = [tid for tid in all_ids if tid not in already_tracked_ids]

                # Insert masivo de los nuevos trackeados (una sola transacción, no N)
                if new_ids:
                    now = datetime.now(timezone.utc).isoformat()
                    conn.executemany(
                        "INSERT OR IGNORE INTO tracked_types (type_id, added_at, reason) VALUES (?, ?, ?)",
                        [(tid, now, "Bulk Panorama General") for tid in new_ids]
                    )
                    conn.commit()
                conn.close()

                progress = st.progress(0, text="Iniciando importación masiva...")
                status = st.empty()
                start_time = time.time()

                def on_progress(done, total, type_id, error):
                    elapsed = time.time() - start_time
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (total - done) / rate if rate > 0 else 0
                    name = names_by_id.get(type_id, f"Type-{type_id}")
                    label = f"{done}/{total} — {name}" + (f" (⚠️ {error})" if error else "")
                    progress.progress(done / total, text=label)
                    status.caption(f"⏱️ Transcurrido: {elapsed:.0f}s — ETA: ~{eta:.0f}s restantes")

                importer = MarketOrdersImporter()
                result_bulk = importer.import_bulk(
                    JITA_REGION_ID, all_ids, progress_callback=on_progress, max_workers=6
                )
                importer.close()

                # Historia de precios (necesaria para que la liquidez no dé 0 siempre —
                # ver fix en app.py / market_history_importer.py)
                status.caption("Importando historial de volumen (para que el scoring de liquidez funcione)...")
                hist_importer = MarketHistoryImporter()

                def on_hist_progress(done, total, type_id, error):
                    progress.progress(done / total, text=f"Historial: {done}/{total} — {names_by_id.get(type_id, type_id)}")

                hist_result = hist_importer.import_bulk(
                    JITA_REGION_ID, all_ids, progress_callback=on_hist_progress, max_workers=6
                )
                hist_importer.close()

                progress.empty()
                status.empty()

                st.success(
                    f"✅ Import completado: {result_bulk['success']} items con order book actualizado, "
                    f"{hist_result['success']} con historial de volumen. "
                    f"{len(new_ids)} nuevos trackeados, {len(already_tracked_ids)} ya lo estaban."
                )
                if result_bulk["failed"]:
                    with st.expander(f"⚠️ {len(result_bulk['failed'])} items con error (ESI o rate limit)"):
                        for tid, err in result_bulk["failed"][:30]:
                            st.caption(f"• {names_by_id.get(tid, tid)}: {err}")
                st.info("Ahora podés ir al Dashboard para ver oportunidades o revisar 'Tracked Items' para gestionarlos.")
                st.rerun()
        except Exception as e:
            st.error(f"Error general: {e}")

    # ============================================================
    # BOTÓN PARA IMPORTAR SDE (CATEGORÍAS Y GRUPOS)
    # ============================================================
    with st.expander("📥 Importar / Actualizar nombres de Categorías y Grupos del SDE de EVE", expanded=False):
        st.caption("Usa los archivos `sde/categories.jsonl` y `sde/groups.jsonl` que están en la carpeta del proyecto.")
        
        if st.button("🚀 Importar SDE Ahora (Categorías + Grupos)", type="primary"):
            # Buscar la raíz del proyecto de forma robusta
            current_file = Path(__file__).resolve()
            project_root = current_file
            while not (project_root / "src").exists() and not (project_root / "sde").exists() and project_root.parent != project_root:
                project_root = project_root.parent

            sde_dir = project_root / "sde"
            cat_file = sde_dir / "categories.jsonl"
            grp_file = sde_dir / "groups.jsonl"

            if not cat_file.exists() or not grp_file.exists():
                st.error("No se encontraron los archivos categories.jsonl y/o groups.jsonl en la carpeta 'sde/' del proyecto.")
            else:
                with st.spinner("Importando categorías y grupos del SDE... Esto puede tardar unos segundos."):
                    try:
                        conn = type_repo._connect()
                        
                        # Crear tablas si no existen (defensivo)
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS categories (
                                id INTEGER PRIMARY KEY,
                                name TEXT NOT NULL,
                                published INTEGER DEFAULT 1
                            )
                        """)
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS groups (
                                id INTEGER PRIMARY KEY,
                                category_id INTEGER NOT NULL,
                                name TEXT NOT NULL,
                                published INTEGER DEFAULT 1
                            )
                        """)
                        
                        # Importar categorías
                        count_cat = 0
                        with open(cat_file, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    obj = json.loads(line)
                                    cat_id = obj.get("_key") or obj.get("id") or obj.get("categoryID")
                                    name = obj.get("name", {}).get("en") if isinstance(obj.get("name"), dict) else obj.get("name")
                                    if cat_id and name:
                                        conn.execute(
                                            "INSERT OR REPLACE INTO categories (id, name, published) VALUES (?, ?, 1)",
                                            (int(cat_id), str(name))
                                        )
                                        count_cat += 1
                        
                        # Importar grupos
                        count_grp = 0
                        with open(grp_file, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    obj = json.loads(line)
                                    grp_id = obj.get("_key") or obj.get("id") or obj.get("groupID")
                                    cat_id = obj.get("categoryID") or obj.get("category_id")
                                    name = obj.get("name", {}).get("en") if isinstance(obj.get("name"), dict) else obj.get("name")
                                    if grp_id and cat_id and name:
                                        conn.execute(
                                            "INSERT OR REPLACE INTO groups (id, category_id, name, published) VALUES (?, ?, ?, 1)",
                                            (int(grp_id), int(cat_id), str(name))
                                        )
                                        count_grp += 1
                        
                        conn.commit()
                        conn.close()
                        
                        st.success(f"✅ Importación completada: {count_cat} categorías y {count_grp} grupos actualizados.")
                        st.info("Los nombres en el explorador ahora deberían ser los reales de EVE. Refrescá la página si es necesario.")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error durante la importación: {e}")

    # --- EXPLORADOR POR CATEGORÍA Y GRUPO ---
    st.markdown("### Explorar por Categoría → Grupo (SDE de EVE)")

    col_cat, col_group = st.columns(2)

    with col_cat:
        categories = type_repo.get_distinct_categories()
        if categories:
            cat_options = {
                f"{c.get('category_id', c.get('id', '?'))} — {c.get('name', c.get('example_name', 'Sin nombre'))} ({c['item_count']} items)": c.get('category_id', c.get('id'))
                for c in categories
            }
            selected_cat_label = st.selectbox(
                "1. Elegí una Categoría",
                options=list(cat_options.keys()),
                index=0,
                key="cat_in_tab"
            )
            selected_cat_id = cat_options[selected_cat_label]
        else:
            st.warning("No se encontraron categorías.")
            selected_cat_id = None

    with col_group:
        if selected_cat_id:
            groups = type_repo.get_groups_by_category(selected_cat_id)
            if groups:
                group_options = {
                    f"{g.get('group_id', g.get('id', '?'))} — {g.get('name', g.get('example_name', 'Grupo'))} ({g['item_count']} items)": g.get('group_id', g.get('id'))
                    for g in groups
                }
                selected_group_label = st.selectbox(
                    "2. Elegí un Grupo",
                    options=list(group_options.keys()),
                    index=0,
                    key="group_in_tab"
                )
                selected_group_id = group_options[selected_group_label]
            else:
                st.info("Esta categoría no tiene grupos.")
                selected_group_id = None
        else:
            selected_group_id = None

    if selected_group_id:
        st.markdown("**Items del grupo seleccionado (seleccioná los que querés analizar):**")
        items_in_group = type_repo.get_types_in_group(selected_group_id, limit=40)

        if items_in_group:
            # Botones de selección masiva
            col_all1, col_all2, _ = st.columns([2, 2, 4])
            with col_all1:
                if st.button("✅ Seleccionar todos", key="select_all_group"):
                    for item in items_in_group:
                        st.session_state[f"bulk_group_{item['id']}"] = True
                    st.rerun()
            with col_all2:
                if st.button("❌ Deseleccionar todos", key="deselect_all_group"):
                    for item in items_in_group:
                        st.session_state[f"bulk_group_{item['id']}"] = False
                    st.rerun()

            # Bulk selection
            selected_ids = []
            for item in items_in_group:
                is_tracked = type_repo.is_tracked(item['id'])
                col1, col2 = st.columns([6.5, 2])
                with col1:
                    label = f"{'✅ ' if is_tracked else ''}{item['name']} (ID: {item['id']})"
                    checked = st.checkbox(label, value=is_tracked, key=f"bulk_group_{item['id']}")
                    if checked:
                        selected_ids.append(item['id'])

            st.divider()

            # Bulk action button with warning
            if selected_ids:
                st.warning(
                    f"⚠️ Vas a trackear e importar **{len(selected_ids)}** items.\n"
                    "Esto puede tardar varios minutos (depende de la cantidad y la velocidad de ESI). "
                    "¿Deseas continuar?"
                )
                if st.button(f"🚀 Trackear + Importar los {len(selected_ids)} seleccionados", type="primary"):
                    names_by_id = {tid: (type_repo.get_name(tid) or f"Type-{tid}") for tid in selected_ids}

                    conn = type_repo._connect()
                    now = datetime.now(timezone.utc).isoformat()
                    conn.executemany(
                        "INSERT OR IGNORE INTO tracked_types (type_id, added_at, reason) VALUES (?, ?, ?)",
                        [(tid, now, "Bulk import from group explorer") for tid in selected_ids]
                    )
                    conn.commit()
                    conn.close()

                    progress = st.progress(0, text="Iniciando importación masiva...")

                    def on_progress(done, total, type_id, error):
                        name = names_by_id.get(type_id, f"Type-{type_id}")
                        progress.progress(done / total, text=f"{done}/{total} — {name}" + (f" (⚠️ {error})" if error else ""))

                    importer = MarketOrdersImporter()
                    result_bulk = importer.import_bulk(
                        JITA_REGION_ID, selected_ids, progress_callback=on_progress, max_workers=6
                    )
                    importer.close()

                    hist_importer = MarketHistoryImporter()

                    def on_hist_progress(done, total, type_id, error):
                        progress.progress(done / total, text=f"Historial: {done}/{total} — {names_by_id.get(type_id, type_id)}")

                    hist_result = hist_importer.import_bulk(
                        JITA_REGION_ID, selected_ids, progress_callback=on_hist_progress, max_workers=6
                    )
                    hist_importer.close()
                    progress.empty()

                    st.success(f"✅ {result_bulk['success']} de {len(selected_ids)} items procesados (órdenes + {hist_result['success']} con historial).")
                    if result_bulk["failed"]:
                        with st.expander(f"⚠️ {len(result_bulk['failed'])} con error"):
                            for tid, err in result_bulk["failed"]:
                                st.caption(f"• {names_by_id.get(tid, tid)}: {err}")
                    st.rerun()
        else:
            st.info("No hay items en este grupo.")

    st.caption("💡 Tip: Usá la pestaña 'Tracked Items' para ver y gestionar todo lo que ya seleccionaste.")