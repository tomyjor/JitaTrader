"""
Dashboard principal de JitaTrader v2.

Regla de capa: esta página NUNCA decide reglas de negocio (umbrales de
score, de liquidez, etc.) -- solo lee lo que OpportunityEngine ya decidió
(`Opportunity.recommendation` / `.recommendation_reason`) y lo pinta.
Antes del Sprint 1, el badge "Compra recomendada" reimplementaba sus
propios umbrales acá mismo, desincronizados del score real y sin acceso
a la señal más importante (volumen diario crudo) -- ver changelog en
`OpportunityEngine`.
"""

import sys
from pathlib import Path


def _find_project_root(start: Path) -> Path:
    """
    Sube directorios hasta encontrar la raíz del proyecto (la que
    contiene `src/`). Más robusto que un `parents[N]` fijo: un índice
    fijo se rompe apenas un archivo se mueve un nivel de profundidad
    -- de hecho, exactamente ese bug existía en
    `pages/02_tracked_items.py` (usaba el mismo índice que este archivo
    pese a estar un nivel más profundo, y apuntaba a una ruta
    inexistente; solo "funcionaba" porque Streamlit corre todas las
    páginas en el mismo proceso que ya había insertado el path correcto
    al cargar este módulo primero).
    """
    current = start
    while not (current / "src").exists() and current.parent != current:
        current = current.parent
    return current


sys.path.insert(0, str(_find_project_root(Path(__file__).resolve()) / "src"))

import streamlit as st
from infrastructure.repositories.sqlite_type_repository import SQLiteTypeRepository, JITA_REGION_ID
from infrastructure.repositories.sqlite_market_repository import SQLiteMarketRepository
from domain.services.opportunity_engine import OpportunityEngine
from application.use_cases.detect_opportunities_use_case import (
    DetectOpportunitiesUseCase, DetectOpportunitiesRequest
)
from domain.value_objects.tax_profile import TaxProfile
from presentation.streamlit_app.components.opportunity_table import (
    render_opportunity_card, show_opportunity_table
)

st.set_page_config(page_title="JitaTrader v2", page_icon="🚀", layout="wide")
st.title("🚀 JitaTrader v2 - Dashboard de Oportunidades de Mercado (Jita)")


@st.cache_resource
def get_repos():
    return SQLiteTypeRepository(), SQLiteMarketRepository()


type_repo, market_repo = get_repos()
engine = OpportunityEngine()
use_case = DetectOpportunitiesUseCase(market_repo, type_repo, engine)
tax = TaxProfile(broker_fee_rate=0.03, sales_tax_rate=0.036)

# === Sidebar controls ===
st.sidebar.header("⚙️ Filtros de Análisis")
min_score = st.sidebar.slider("Score mínimo de oportunidad", 40, 95, 55, step=1)
max_results = st.sidebar.slider("Máx. oportunidades a mostrar", 5, 50, 20)

st.sidebar.divider()
st.sidebar.subheader("📋 Watchlist actual")

tracked = type_repo.tracked_type_ids()

if tracked:
    st.sidebar.success(f"**{len(tracked)}** productos trackeados")
    for tid in tracked[:8]:  # mostrar primeros
        name = type_repo.get_name(tid) or f"ID {tid}"
        st.sidebar.write(f"• {name}")
    if len(tracked) > 8:
        st.sidebar.caption(f"... y {len(tracked)-8} más")

    if st.sidebar.button("🔄 Refrescar import de todos los trackeados"):
        with st.spinner("Re-importando order books de toda la watchlist desde ESI..."):
            from infrastructure.esi.market_orders_importer import MarketOrdersImporter
            importer = MarketOrdersImporter()
            errors = []
            for tid in tracked:
                try:
                    importer = MarketOrdersImporter()  # nuevo cliente por si hay rate limit
                    importer.import_type_orders(JITA_REGION_ID, tid)
                except Exception as e:
                    errors.append((tid, str(e)))
        if errors:
            st.sidebar.warning(f"Import completado con {len(errors)} error(es):")
            for tid, err in errors[:5]:
                st.sidebar.caption(f"• ID {tid}: {err}")
        else:
            st.sidebar.success("Import completado sin errores. Recargando análisis...")
        st.rerun()

    if st.sidebar.button("📈 Importar volumen histórico (fix liquidez/score)"):
        st.sidebar.caption("Esto llena `market_history`. Sin esto, el componente de liquidez de "
                            "TODOS los ítems queda en 0 (ver nota en el desglose del score).")
        history_progress = st.sidebar.progress(0, text="Importando historia de precios...")
        from infrastructure.esi.market_history_importer import MarketHistoryImporter
        importer = MarketHistoryImporter()

        def on_hist_progress(done, total, type_id, error):
            history_progress.progress(done / total, text=f"{done}/{total} items procesados")

        result_hist = importer.import_bulk(JITA_REGION_ID, tracked, progress_callback=on_hist_progress, max_workers=6)
        importer.close()
        history_progress.empty()
        st.sidebar.success(f"✅ Historia importada para {result_hist['success']} de {len(tracked)} items.")
        if result_hist["failed"]:
            with st.sidebar.expander(f"⚠️ {len(result_hist['failed'])} fallaron"):
                for tid, err in result_hist["failed"][:10]:
                    st.caption(f"• ID {tid}: {err}")
        st.rerun()
else:
    st.sidebar.info("Modo Discovery: mostrando mejores oportunidades del mercado general.")

# === Main logic ===
if not tracked:
    st.info("📌 **Modo Discovery activado** — Mostrando las mejores oportunidades del mercado Jita con datos reales.")
    st.caption("Se buscan items que tengan order book activo (compra + venta). Trackeá items específicos desde 'Tracked Items' para análisis más profundos y automáticos.")

    # Query mejorada para Discovery: items con order book bidireccional.
    # GROUP BY + HAVING evita dos sub-queries EXISTS correlacionadas por fila
    # (ese patrón anterior escaneaba la tabla completa dos veces por cada type_id candidato).
    conn = market_repo._connect()
    rows = conn.execute("""
        SELECT type_id, MAX(fetched_at) as last_fetch
        FROM market_orders
        WHERE region_id = ?
        GROUP BY type_id
        HAVING SUM(CASE WHEN is_buy_order = 1 THEN 1 ELSE 0 END) > 0
           AND SUM(CASE WHEN is_buy_order = 0 THEN 1 ELSE 0 END) > 0
        ORDER BY last_fetch DESC
        LIMIT 300
    """, (JITA_REGION_ID,)).fetchall()
    conn.close()

    type_ids = [r["type_id"] for r in rows] if rows else []
    if type_ids:
        st.caption(f"Se encontraron {len(type_ids)} items con order book activo. Se mostrarán los mejores según scoring.")
    else:
        st.warning(
            "No se encontró ningún ítem con order book bidireccional (compra + venta) en la base. "
            "Andá a **Tracked Items → Buscar y Agregar** y usá el botón de importación masiva "
            "('Panorama General') para poblar datos, o trackeá algunos items puntuales."
        )
else:
    st.success(f"🎯 Analizando tus **{len(tracked)}** productos trackeados en Jita.")
    type_ids = tracked

if not type_ids:
    st.info("Tip: Trackeá algunos productos desde la página 'Tracked Items' o ejecutá el importador manualmente para poblar market_orders.")
else:
    request = DetectOpportunitiesRequest(type_ids=type_ids, region_id=JITA_REGION_ID, tax_profile=tax)

    with st.spinner("Ejecutando motores analíticos (ROI, Liquidez, Riesgo, Competencia, Exit Time)..."):
        result = use_case.execute(request, min_score=min_score, max_results=max_results)

    # SIEMPRE mostramos lo mejor disponible, sea Discovery o Tracked: usamos
    # ranked_all (sin filtrar por min_score) como fallback cuando el filtro
    # deja 0 resultados, para que el usuario nunca se quede en blanco si hay
    # evidencia suficiente para al menos un item.
    is_discovery = len(tracked) == 0

    if result.opportunities:
        opportunities_to_show = result.opportunities
        label = "Mejores Oportunidades en Jita" if is_discovery else "Oportunidades Detectadas"
        st.subheader(f"📊 {label} ({len(opportunities_to_show)} de {result.summary.get('con_evidencia_suficiente', 0)} con datos)")
    elif result.ranked_all:
        opportunities_to_show = result.ranked_all[:15]
        st.warning(
            f"⚠️ Ninguno de los {len(result.ranked_all)} items con datos reales superó tu score mínimo ({min_score}). "
            f"Mostrando los {len(opportunities_to_show)} mejores igual, para que siempre tengas algo que mirar — "
            "pero ojo, esto no es una recomendación de compra, es 'lo menos malo disponible ahora'. "
            "Bajá el slider de score mínimo en la barra lateral si querés ver más."
        )
        st.subheader(f"📊 Mejores {len(opportunities_to_show)} disponibles (todos por debajo de {min_score})")
    else:
        opportunities_to_show = []
        st.subheader("📊 Oportunidades Detectadas (0 con datos)")

    if opportunities_to_show:
        view_mode = st.radio(
            "Vista",
            ["🗂️ Tarjetas (detalle + desglose)", "📊 Tabla (ordenable por columna)"],
            horizontal=True,
            label_visibility="collapsed",
            key="dashboard_view_mode",
        )
        if view_mode.startswith("📊"):
            show_opportunity_table(opportunities_to_show)
            st.caption(
                "💡 Click en el header de cualquier columna (Score, ROI %, Liquidez, etc.) "
                "para ordenar — de nuevo para invertir el orden."
            )
        else:
            for r in opportunities_to_show:
                render_opportunity_card(r)
    else:
        if result.summary.get("con_evidencia_suficiente", 0) == 0:
            st.info("Ninguno de los productos evaluados tiene snapshots completos de order book todavía. "
                    "Si recién los trackeaste, el import automático debería haberlos poblado. Refrescá la página.")

    # Resumen mejorado (formato legible)
    with st.expander("📈 Resumen del análisis", expanded=False):
        s = result.summary

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Items evaluados", s.get("type_ids_evaluados", 0))
        c2.metric("Con datos reales", s.get("con_evidencia_suficiente", 0))
        c3.metric("Oportunidades encontradas", s.get("oportunidades", 0))
        c4.metric("Score mínimo usado", f"{s.get('min_score_usado', 55):.0f}")

        _summary_pool = result.opportunities if result.opportunities else opportunities_to_show
        if _summary_pool:
            avg_score = sum(r.value.score for r in _summary_pool) / len(_summary_pool)
            avg_roi = sum(r.value.roi_percent for r in _summary_pool) / len(_summary_pool)
            n_no_volume = sum(1 for r in _summary_pool if not r.value.score_breakdown.get("has_volume_evidence", True))
            st.success(f"**Promedio de las mostradas:** Score {avg_score:.1f}  |  ROI {avg_roi:.1f}%")
            if n_no_volume:
                st.caption(f"📉 {n_no_volume} de {len(_summary_pool)} ítems mostrados no tienen historial de "
                           "volumen importado (liquidez tratada conservadoramente como desconocida).")

        if result.skipped:
            st.markdown("**Items excluidos (sin datos suficientes):**")
            skipped_data = []
            for tid, motivo in result.skipped[:15]:
                name = type_repo.get_name(tid) or f"ID {tid}"
                skipped_data.append({"Item": name, "Motivo": motivo})

            if skipped_data:
                st.dataframe(skipped_data, use_container_width=True, hide_index=True)

            if len(result.skipped) > 15:
                st.caption(f"... y {len(result.skipped) - 15} más.")

st.divider()
st.caption("JitaTrader v2 • Clean Architecture + DDD • Datos en tiempo real desde ESI (Tranquility) • Actualizado automáticamente al trackear/quitar items")
