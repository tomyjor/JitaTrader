# JitaTrader v2

**Decision Intelligence System for EVE Online (Jita Trading)**

## Novedad v0.3.1 — Sesgo de muestreo en bulk import + vistas ordenables

✅ **Bug real encontrado**: el import masivo "Panorama General" traía `ORDER BY name LIMIT N`
   -- al ordenar alfabéticamente, la muestra quedaba sistemáticamente concentrada en variantes
   narrativas/de facción (ítems que empiezan con comilla, ej. `'Basic' X`), que casi nunca se
   comercian en Jita. Con 400 ítems así trackeados, el 100% mostraba liquidez 0 -- no porque el
   motor estuviera roto, sino porque la muestra estaba sesgada hacia lo menos líquido del juego.
   Cambiado a `ORDER BY RANDOM()`. Cap del slider subido de 400 a 2000 (tu SDE tiene ~27.000
   ítems publicados; 400 nunca fue "todos los items", era el tope arbitrario del slider).
✅ Estimación de tiempo del import masivo corregida (contaba solo la fase de órdenes, no la de
   historial de volumen que corre inmediatamente después -- estaba subestimada a la mitad).
✅ **Vista de tabla ordenable** (Dashboard y Tracked Items): toggle 🗂️ Tarjetas / 📊 Tabla —
   la tabla usa `st.dataframe`, que ya soporta ordenar por click en cualquier columna (Score,
   ROI %, Liquidez, etc.) sin código adicional. En Tracked Items arranca en modo Tabla
   automáticamente si tenés más de 50 ítems trackeados (renderizar cientos de checkboxes +
   badges + expanders individuales es pesado para el navegador).
✅ `scripts/diagnose_liquidity.py`: script nuevo para inspeccionar los números crudos de
   liquidez (`daily_volume`, `total_sell_volume_remain`, etc.) de tu watchlist real y distinguir
   "sesgo de muestra" de "bug real" sin tener que confiar en una explicación — mirá vos los datos.

## Novedad v0.3 (Sprint 1 — Julio 2026) — Fix de scoring saturado + transparencia

✅ **Bug real identificado y corregido**: ítems con ROI muy distinto (ej. 292% / 1558% / 3559%)
   terminaban con scores casi idénticos cuando tenían baja liquidez. La causa NO era una sola:
   1. `roi_component` y `spread_quality` saturaban a partir de ~139% / ~46% respectivamente
      (rango logarítmico demasiado angosto) — ver `OpportunityEngine` (formula_version `log_v2`).
   2. **La causa más grave**: `LiquidityEngine` podía dar hasta 40/100 de liquidez a un ítem con
      **cero** volumen diario real, solo por tener mucho `volume_remain` estancado en el book
      ("order book fantasma"). Corregido con media geométrica (MATH-002 v1.4).
   3. El badge "Compra recomendada" vivía hardcodeado en `app.py` (Streamlit), desincronizado del
      score real. Ahora es una regla de dominio (`OpportunityEngine._classify_recommendation` +
      `Opportunity.recommendation`), la única fuente de verdad para la UI.
✅ `score_breakdown` rediseñado: cada componente vive en escala 0-100 propia, los pesos declarados
   son literalmente los que se aplican, y la suma de contribuciones coincide con el score final
   (auditable, ver `sum_of_contributions`).
✅ `CompetitionEngine`: corregido bug de escala (`order_pressure` vivía en [0,1] pero se pesaba
   como si estuviera en [0,100] — MATH-003 v1.1) y wireado `total_buy_volume` real (antes hardcodeado en 0.0).
✅ **Addendum:** `price_spread_percent` eliminado de `CompetitionEngine` (MATH-003 v1.2) — su signo
   estaba invertido respecto a la propia definición del documento (spread ancho ≠ más competencia)
   y, corregido o no, era redundante con `roi_component`/`spread_quality`. Ver changelog en
   `CompetitionEngine` y `math/MATH-003_Competition.md`. Sin efecto observable en resultados previos
   (nunca estuvo conectado). `pytest` ahora corre sin configurar `PYTHONPATH` a mano (ver sección Tests).
✅ `get_daily_volume` ahora promedia una ventana de 7 días en vez de un solo día (menos ruido).
✅ Reintentos con backoff en `ESIClient` ante errores transitorios de ESI durante imports masivos.
✅ Eliminado código muerto (`esi_live_market_repository.py`, `scripts/jita_analyze.py` — ambos
   pertenecían a una generación de arquitectura anterior e incompatible con la actual).
✅ 22 tests unitarios (11 nuevos, cubriendo específicamente estos fixes) — dominio 100% puro, sin I/O.

## Novedad v0.2 (Julio 2026) — Importación Automática

✅ **Al trackear un producto desde la GUI Streamlit, el order book se importa automáticamente desde ESI (Jita).**
✅ **Al quitarlo de la watchlist, se borra su snapshot de órdenes activas (manteniendo la DB limpia).**
✅ Ya no hace falta correr scripts bash manualmente para cada item. Todo fluye desde la interfaz.

## Estado Actual

- ✅ MATH Suite v1.3 aprobada por Gemini
- ✅ Clean Architecture + DDD completa
- ✅ Value Objects inmutables + Domain Services (ROIEngine, Liquidity, Risk, Competition, ExitTime, OpportunityEngine)
- ✅ Repositorios SQLite reales + Puerto abstracto
- ✅ Importador ESI modular (por región o por type individual)
- ✅ **GUI Streamlit con importación automática al trackear + limpieza al deseleccionar**
- ✅ Use Case DetectOpportunitiesUseCase con exclusión estricta cuando falta evidencia real
- ✅ Modo Discovery mejorado cuando no hay watchlist

## Cómo usar (nuevo flujo recomendado)

1. `cd JitaTrader_v2`
2. `streamlit run src/presentation/streamlit_app/app.py`
3. En la sidebar → "Tracked Items" (o navegación multi-página)
4. Buscá un item (ej: "Caldari Navy Scourge" o "Tritanium")
5. Click en **"➕ Trackear + Importar"** → ¡Automáticamente se agrega y descarga el order book actual!
6. Volvé al Dashboard principal → el análisis se actualiza solo.
7. Para quitar: botón 🗑️ Quitar → se elimina de tracked y se limpia su market_orders.

## Estructura

```
src/
├── domain/
│   ├── value_objects/     ← Money, TaxProfile, Opportunity, Risk, Liquidity, RecommendationLevel...
│   ├── services/          ← ROIEngine, LiquidityEngine, CompetitionEngine, OpportunityEngine...
│   └── ports/              ← MarketRepository, TypeRepository (interfaces)
├── infrastructure/
│   ├── esi/               ← ESIClient (con reintentos) + MarketOrdersImporter + MarketHistoryImporter
│   └── repositories/      ← SQLiteTypeRepository (con untrack + auto-clean), SQLiteMarketRepository
├── application/
│   └── use_cases/         ← DetectOpportunitiesUseCase
├── presentation/
│   └── streamlit_app/
│       ├── app.py              ← Dashboard
│       ├── pages/               ← Tracked Items (gestión + score inline por ítem)
│       └── components/          ← opportunity_table.py: renderizado compartido (badge + breakdown)
└── shared/
```

## Principios (sin cambios)

- Dominio puro (sin Pandas, sin SQL, sin HTTP en domain)
- Inmutabilidad total de Value Objects
- Determinismo + tests
- Explicabilidad (AnalysisResult con confidence + evidence; score_breakdown auditable)
- Separación estricta de concerns (Ports & Adapters) — las reglas de recomendación viven en
  `OpportunityEngine`, nunca en la capa de presentación

## Próximos pasos recomendados

1. Recalibrar los umbrales de recomendación (`OpportunityEngine.RECOMMEND_MIN_SCORE`, etc.) con
   uso real una vez que haya más historial de trading -- son constantes de clase, fáciles de tunear.
2. Agregar PortfolioOptimizer (MATH-007)
3. Mejorar UI con gráficos (Plotly) y alertas
4. Añadir Experience Layer / aprendizaje de predicciones pasadas (MATH-006 + RFC-007)

## Tests

```bash
pip install -e ".[dev]"
pytest
```

`pytest` ya sabe encontrar `src/` solo (configurado en `pyproject.toml` vía
`[tool.pytest.ini_options] pythonpath = ["src"]`) -- no hace falta setear
`PYTHONPATH` a mano. Para ver más detalle por test: `pytest -v`. Para correr
solo un archivo: `pytest tests/domain/services/test_opportunity_engine.py -v`.

## Requisitos

```bash
pip install -e .
# o
pip install streamlit requests
```

**Nota**: Necesita internet para llamadas ESI. La primera vez que trackeás un item puede tardar 1-3 segundos por item (rate limit respetado).

¡Disfrutá el trading informado en Jita! 🚀
