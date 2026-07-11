PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS item_types (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    group_id INTEGER,
    category_id INTEGER,
    market_group_id INTEGER,
    volume REAL,
    base_price REAL,
    published INTEGER
);

CREATE INDEX IF NOT EXISTS idx_item_name
ON item_types(name);

CREATE INDEX IF NOT EXISTS idx_group
ON item_types(group_id);


-- Catálogo de regiones de ESI (/universe/regions/). Se puebla una sola vez,
-- cambia casi nunca. Es la tabla que permite comparar "todas las regiones"
-- sin hardcodear ids sueltos en el código.
CREATE TABLE IF NOT EXISTS regions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);


-- Serie diaria de precio/volumen por producto y por región.
-- Fuente: GET /markets/{region_id}/history/
-- Se acumula con el tiempo (a diferencia de market_orders), por eso la
-- clave primaria incluye la fecha: cada día es una fila nueva, no se pisa.
CREATE TABLE IF NOT EXISTS market_history (
    region_id INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    average REAL,
    highest REAL,
    lowest REAL,
    volume INTEGER,
    order_count INTEGER,
    PRIMARY KEY (region_id, type_id, date),
    FOREIGN KEY (region_id) REFERENCES regions(id),
    FOREIGN KEY (type_id) REFERENCES item_types(id)
);

CREATE INDEX IF NOT EXISTS idx_history_type
ON market_history(type_id);

CREATE INDEX IF NOT EXISTS idx_history_region
ON market_history(region_id);


-- Foto del order book activo por región.
-- Fuente: GET /markets/{region_id}/orders/
-- A DIFERENCIA de market_history, esto NO es una serie histórica: una orden
-- que ya no existe en ESI (cancelada o completada) tiene que desaparecer de
-- acá. El importador debe borrar las órdenes viejas de una región antes de
-- insertar el snapshot nuevo (o hacer DELETE WHERE region_id=? antes del
-- INSERT), si no la tabla va a acumular basura de órdenes que ya no están
-- vigentes y el cálculo de competencia/liquidez va a quedar mal.
CREATE TABLE IF NOT EXISTS market_orders (
    order_id INTEGER PRIMARY KEY,
    region_id INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    is_buy_order INTEGER NOT NULL,
    price REAL NOT NULL,
    volume_remain INTEGER NOT NULL,
    volume_total INTEGER NOT NULL,
    min_volume INTEGER,
    duration INTEGER,
    issued TEXT,
    location_id INTEGER,
    order_range TEXT,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (region_id) REFERENCES regions(id),
    FOREIGN KEY (type_id) REFERENCES item_types(id)
);

CREATE INDEX IF NOT EXISTS idx_orders_type_region
ON market_orders(type_id, region_id);

CREATE INDEX IF NOT EXISTS idx_orders_region
ON market_orders(region_id);


-- Watchlist: productos que de verdad queremos trackear en detalle.
-- Con ~50k types publicados x 113 regiones, importar TODO por defecto no es
-- viable ni tiene sentido (la mayoría de los items no se comercian nunca).
-- Esta tabla es la que decide el alcance real de lo que se importa: el
-- importador de history/orders debe iterar sobre tracked_types, no sobre
-- todo item_types. Arranca vacía a propósito -- se puebla a mano o desde
-- repo.search() cuando encuentres algo que quieras seguir.
CREATE TABLE IF NOT EXISTS tracked_types (
    type_id INTEGER PRIMARY KEY,
    added_at TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY (type_id) REFERENCES item_types(id)
);


-- ============================================================
-- TABLAS DEL SDE DE EVE (categorías y grupos reales)
-- ============================================================

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    published INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY,
    category_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    published INTEGER DEFAULT 1,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE INDEX IF NOT EXISTS idx_groups_category ON groups(category_id);
CREATE INDEX IF NOT EXISTS idx_groups_name ON groups(name);


-- Snapshot diario AGREGADO de competencia/liquidez del order book, por
-- región y producto. No es un dump de cada orden en cada fecha -- guardar
-- cada order_id de cada día multiplicaría el tamaño de la base sin agregar
-- información útil para Market DNA (no nos importa la orden #12345 en sí,
-- nos importa "cuánta competencia había ese día"). Por eso esta tabla
-- resume lo que market_orders (la foto del momento) tiene en un instante
-- dado, y se acumula día a día para poder ver la evolución.
CREATE TABLE IF NOT EXISTS market_order_snapshots (
    region_id INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,
    buy_order_count INTEGER NOT NULL,
    sell_order_count INTEGER NOT NULL,
    best_buy_price REAL,
    best_sell_price REAL,
    total_volume_remain INTEGER,
    PRIMARY KEY (region_id, type_id, snapshot_date),
    FOREIGN KEY (region_id) REFERENCES regions(id),
    FOREIGN KEY (type_id) REFERENCES item_types(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_type
ON market_order_snapshots(type_id);
