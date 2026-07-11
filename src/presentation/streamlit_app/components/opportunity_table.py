"""
Componente reutilizable de presentación para mostrar Opportunities.

Centraliza acá el renderizado del badge de recomendación y del desglose
del score para que Dashboard (`app.py`) y Tracked Items
(`pages/02_tracked_items.py`) muestren exactamente lo mismo, de la misma
forma. Antes de este cambio, este archivo era un componente sin usar
mientras `app.py` reimplementaba su propio renderizado inline -- ahora es
la única fuente de la lógica de presentación de una Opportunity.

Importante: este módulo solo PINTA datos que el dominio ya calculó
(`Opportunity.recommendation`, `.score_breakdown`, etc.). Nunca decide
umbrales ni reglas de negocio -- esas viven en `OpportunityEngine`.
"""

from typing import List, Dict, Any

import streamlit as st

from domain.value_objects.recommendation import RecommendationLevel

# Cómo se pinta cada RecommendationLevel. Único lugar de la UI que
# traduce la categoría de dominio a colores/iconos -- el TEXTO de la
# razón siempre viene de `recommendation_reason`, calculado por el
# motor, nunca hardcodeado acá.
_BADGE_STYLE = {
    RecommendationLevel.BUY: ("success", "✅"),
    RecommendationLevel.CAUTION_LOW_LIQUIDITY: ("warning", "⚠️"),
    RecommendationLevel.CAUTION_NO_VOLUME_DATA: ("warning", "📉"),
    RecommendationLevel.CAUTION_HIGH_RISK: ("warning", "🔥"),
    RecommendationLevel.NEUTRAL: (None, None),
}


def render_recommendation_badge(opportunity) -> None:
    """Pinta el badge de recomendación leyendo SOLO lo que ya calculó el dominio."""
    kind, icon = _BADGE_STYLE.get(opportunity.recommendation, (None, None))
    if kind is None:
        return
    message = f"{icon} **{opportunity.recommendation_reason}**"
    if kind == "success":
        st.success(message, icon=icon)
    else:
        st.warning(message, icon=icon)


def render_score_breakdown(score_breakdown: Dict[str, Any]) -> None:
    """
    Renderiza la tabla de desglose del score de forma genérica a partir
    de `score_breakdown["components"]`, sin hardcodear filas -- si
    OpportunityEngine agrega o quita un componente, la tabla se
    actualiza sola. Cada fila muestra raw_value * weight = contribution
    de forma literal (ver `OpportunityEngine._build_score_breakdown`).
    """
    components = score_breakdown.get("components", {})
    if not components:
        st.caption("Sin desglose disponible para esta oportunidad.")
        return

    rows = ["| Componente | Valor (0-100) | Peso | Contribución |", "|---|---|---|---|"]
    for comp in components.values():
        rows.append(
            f"| {comp['label']} | {comp['raw_value']:.1f} | {comp['weight']:.2f} | "
            f"{comp['contribution']:.2f} |"
        )
    st.markdown("\n".join(rows))

    final_score = score_breakdown.get("final_score", 0)
    checksum = score_breakdown.get("sum_of_contributions", final_score)
    st.markdown(f"**Score Final = {final_score}** (`{score_breakdown.get('formula_version', 'v1')}`)")
    st.caption(
        f"✔️ Chequeo de transparencia: la suma de todas las contribuciones da {checksum} "
        f"— debe coincidir con el score final salvo redondeo. Si no coincide, hay un bug."
    )

    if not score_breakdown.get("has_volume_evidence", True):
        st.caption(
            "📉 Este ítem no tiene ningún día de volumen histórico importado todavía "
            "(`market_history` vacía para este type_id). Su componente de liquidez es 0 "
            "por diseño hasta que se importe historial real — no es una liquidez confirmada "
            "en 0, es una liquidez *desconocida* tratada de forma conservadora."
        )


def render_opportunity_card(result) -> None:
    """
    Renderiza una Opportunity completa (métricas + badge + desglose
    colapsable) dentro de un `st.container(border=True)`. Es el bloque
    de UI que usan tanto el Dashboard como Tracked Items para mostrar
    cada ítem de forma consistente.

    `result` es un AnalysisResult[Opportunity] (tiene `.value` y
    `.confidence`), tal como lo devuelve OpportunityEngine.detect().
    """
    o = result.value
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([3.5, 1.2, 1.2, 1.2, 1.5])
        c1.markdown(f"**{o.type_name}**  \n`ID: {o.type_id}`")
        c2.metric("Score", f"{o.score:.1f}")
        c3.metric("ROI %", f"{o.roi_percent:.1f}")
        c4.metric("Riesgo", o.risk.risk_level)
        c5.metric("Liquidez", f"{o.liquidity.liquidity_score:.0f}")

        st.caption(f"💰 Buy: {o.buy_price}  |  Sell: {o.sell_price}  |  Confianza análisis: {result.confidence:.0f}%")

        render_recommendation_badge(o)

        if o.score_breakdown:
            with st.expander("🔍 Ver cálculo del score"):
                render_score_breakdown(o.score_breakdown)


def show_opportunity_table(opportunities: List) -> None:
    """
    Muestra una tabla compacta (una fila por ítem) de oportunidades,
    incluyendo la recomendación de dominio. Útil para vistas resumidas
    donde una tarjeta completa por ítem sería demasiado (p.ej. listas
    largas en Tracked Items).
    """
    if not opportunities:
        st.info("No hay oportunidades para mostrar.")
        return

    data = []
    for r in opportunities:
        o = r.value
        data.append({
            "Item": o.type_name,
            "Score": round(o.score, 1),
            "ROI %": round(o.roi_percent, 1),
            "Riesgo": o.risk.risk_level,
            "Liquidez": round(o.liquidity.liquidity_score, 1),
            "Recomendación": o.recommendation.value,
            "Buy Price": o.buy_price.amount,
            "Sell Price": o.sell_price.amount,
        })

    st.dataframe(data, use_container_width=True, hide_index=True)
