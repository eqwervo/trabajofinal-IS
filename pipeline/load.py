"""
load.py
-------
Tercera etapa del pipeline ETL de IceStats.
Recibe los DataFrames ya transformados y los persiste en PostgreSQL.

¿Por qué SQLAlchemy?
  SQLAlchemy es una librería de Python que actúa como intermediario entre
  el código y la base de datos. En vez de escribir SQL puro, le pasamos
  DataFrames y ella se encarga de generar los INSERT necesarios.
  Además, gestiona el "pool" de conexiones (reutilización de conexiones
  abiertas) para no abrir/cerrar una conexión por cada operación.

Flujo general:
  1. Leer DATABASE_URL del entorno (definida en docker-compose.yml)
  2. Crear el motor de conexión (Engine) con SQLAlchemy
  3. Para cada tabla: crearla si no existe, luego insertar los datos
  4. Los tiros (~1.7M filas) se cargan en lotes para no saturar la memoria

Uso típico:
  from pipeline.load import load_all
  load_all(transformed_data)   # transformed_data viene de transform.transform_all()
"""

import os
import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Tamaño de lote para la carga de tiros ─────────────────────────────────────
# Con ~1.7M filas, cargar todo de una vez consumiría demasiada memoria.
# Dividimos la carga en bloques de CHUNK_SIZE filas.
# Valor elegido como balance entre velocidad y uso de memoria.
CHUNK_SIZE = 100_000


# ── Conexión ──────────────────────────────────────────────────────────────────

def get_engine():
    """
    Crea y retorna un Engine de SQLAlchemy usando la variable de entorno
    DATABASE_URL.

    ¿Qué es un Engine?
      Es el objeto central de SQLAlchemy. Representa la conexión a la base
      de datos y gestiona internamente un pool de conexiones reutilizables.
      No abre la conexión al crearse — la abre la primera vez que se necesita.

    La DATABASE_URL tiene el formato:
      postgresql://usuario:contraseña@host:puerto/nombre_db
      Ejemplo: postgresql://icestats:icestats@db:5432/icestats
                                                  ^^
                                                  'db' es el nombre del servicio
                                                  en docker-compose.yml, que Docker
                                                  resuelve automáticamente como hostname.

    Si la variable no está definida, lanza un error claro para que el
    desarrollador sepa qué configurar.
    """
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        raise EnvironmentError(
            "La variable de entorno DATABASE_URL no está definida.\n"
            "Asegurate de correr la app con docker-compose, o de setear\n"
            "DATABASE_URL manualmente para desarrollo local.\n"
            "Ejemplo: export DATABASE_URL=postgresql://icestats:icestats@localhost:5432/icestats"
        )

    # create_engine() no abre la conexión todavía — solo la configura.
    # pool_pre_ping=True hace que SQLAlchemy verifique que la conexión siga
    # activa antes de usarla (útil si el contenedor de Postgres se reinició).
    engine = create_engine(db_url, pool_pre_ping=True)
    logger.info(f"Engine creado para: {db_url}")
    return engine


# ── Creación de tablas ────────────────────────────────────────────────────────

# DDL (Data Definition Language): sentencias SQL que definen la estructura
# de las tablas. Usamos IF NOT EXISTS para que sean idempotentes — es decir,
# podemos ejecutarlas múltiples veces sin error (si la tabla ya existe, no hace nada).

SHOTS_DDL = """
CREATE TABLE IF NOT EXISTS shots (
    -- PK surrogate: auto-incremental, Postgres la genera sola en cada INSERT/COPY
    -- No va en el DataFrame → el COPY la ignora y la secuencia la rellena
    "id"                   BIGSERIAL PRIMARY KEY,

    -- Identificadores del tiro (no únicos por sí solos entre temporadas)
    "shotID"               INTEGER,
    "season"               SMALLINT,
    "isPlayoffGame"        SMALLINT,
    "game_id"              INTEGER,

    -- Tiempo y período del partido
    "time"                 SMALLINT,
    "period"               SMALLINT,

    -- Equipos participantes
    "homeTeamCode"         VARCHAR(10),
    "awayTeamCode"         VARCHAR(10),
    "team"                 VARCHAR(10),
    "isHomeTeam"           SMALLINT,
    "homeTeamWon"          SMALLINT,

    -- Marcador al momento del tiro
    "homeTeamGoals"        SMALLINT,
    "awayTeamGoals"        SMALLINT,

    -- Métricas esperadas (xGoal = probabilidad de gol según el modelo)
    "goal"                 SMALLINT,
    "xGoal"                REAL,
    "xFroze"               REAL,
    "xRebound"             REAL,
    "xShotWasOnGoal"       REAL,

    -- Ubicación del tiro (coordenadas ajustadas por arena)
    "xCordAdjusted"        REAL,
    "yCordAdjusted"        REAL,
    "arenaAdjustedShotDistance" REAL,
    "shotAngle"            REAL,

    -- Características del disparo
    "shotType"             VARCHAR(20),
    "shotWasOnGoal"        SMALLINT,
    "shotOnEmptyNet"       SMALLINT,
    "shotRebound"          SMALLINT,
    "shotRush"             SMALLINT,
    "shotGeneratedRebound" SMALLINT,

    -- Situación numérica
    "homeSkatersOnIce"     SMALLINT,
    "awaySkatersOnIce"     SMALLINT,
    "homeEmptyNet"         SMALLINT,
    "awayEmptyNet"         SMALLINT,

    -- Jugadores involucrados
    "shooterPlayerId"      INTEGER,
    "shooterName"          VARCHAR(100),
    "goalieIdForShot"      INTEGER,
    "goalieNameForShot"    VARCHAR(100),
    "playerPositionThatDidEvent" VARCHAR(20),

    -- Columnas derivadas (calculadas en transform.py)
    "gameSituation"        VARCHAR(10),   -- '5v5', 'PP', 'PK', 'EN', 'other'
    "dangerZone"           VARCHAR(10),   -- 'high', 'medium', 'low'
    "isClutchSituation"    BOOLEAN        -- True si es momento de alta presión
);
"""

SHOTS_INDEXES = [
    # Filtro más frecuente en todas las queries del dashboard
    'CREATE INDEX IF NOT EXISTS idx_shots_season ON shots ("season")',
    # Queries de equipo (tab Directivos y Entrenador)
    'CREATE INDEX IF NOT EXISTS idx_shots_teams ON shots ("homeTeamCode", "awayTeamCode")',
    # Queries de jugador (tab Reclutador — ranking y perfil)
    'CREATE INDEX IF NOT EXISTS idx_shots_shooter ON shots ("shooterName", "season")',
    # Filtro de situación de juego (5v5, PP, PK, etc.)
    'CREATE INDEX IF NOT EXISTS idx_shots_situation ON shots ("gameSituation")',
    # Filtro clutch (RF-R04)
    'CREATE INDEX IF NOT EXISTS idx_shots_clutch ON shots ("isClutchSituation")',
    # Queries de portero (RF-R03)
    'CREATE INDEX IF NOT EXISTS idx_shots_goalie ON shots ("goalieNameForShot", "season")',
    # Índice compuesto para queries de equipo + temporada (las más comunes)
    'CREATE INDEX IF NOT EXISTS idx_shots_season_teams ON shots ("season", "homeTeamCode", "awayTeamCode")',
]


def create_tables(engine) -> None:
    """
    Crea la tabla shots y sus índices en PostgreSQL.

    Teams y players se crean automáticamente via pandas to_sql(if_exists='replace')
    con todas sus columnas reales — no necesitan DDL manual.

    Los índices se crean con IF NOT EXISTS, por lo que son idempotentes:
    se pueden ejecutar múltiples veces sin error.
    """
    logger.info("Creando tabla shots e índices...")
    with engine.connect() as conn:
        conn.execute(text(SHOTS_DDL))
        conn.commit()
    logger.info("Tabla shots verificada ✓")


def create_indexes(engine) -> None:
    """
    Crea los índices de la tabla shots.
    Se llama DESPUÉS de load_shots_streaming porque los índices sobre una
    tabla vacía son inútiles y ralentizan el COPY. Crearlos al final es
    más rápido que mantenerlos durante la carga masiva.
    """
    logger.info("Creando índices en tabla shots...")
    with engine.connect() as conn:
        for idx_sql in SHOTS_INDEXES:
            name = idx_sql.split("idx_")[1].split(" ")[0]
            logger.info(f"  → idx_{name}")
            conn.execute(text(idx_sql))
        conn.commit()
    logger.info(f"Índices creados: {len(SHOTS_INDEXES)} ✓")


# ── Método de carga COPY ─────────────────────────────────────────────────────

def _copy_method(table, conn, keys, data_iter):
    """
    Método de inserción usando COPY nativo de PostgreSQL.

    ¿Por qué COPY en vez de INSERT?
      INSERT genera una sentencia SQL por cada lote y Postgres debe parsearla,
      planificarla y ejecutarla. COPY es un protocolo binario interno de Postgres
      diseñado específicamente para carga masiva — escribe los datos directamente
      en las páginas del disco sin pasar por el motor de consultas.
      Resultado: 5-10x más rápido que INSERT para volúmenes grandes.

    ¿Cómo funciona?
      1. Tomamos la conexión "cruda" de psycopg2 (el driver de Postgres)
      2. Serializamos las filas a formato TSV (tab-separated) en memoria (StringIO)
      3. Los valores NULL se representan como \\N (convención de COPY)
      4. cur.copy_from() envía el buffer a Postgres con el protocolo COPY

    Este método se pasa como parámetro `method` a pandas to_sql().
    pandas lo llama automáticamente por cada lote de filas.
    """
    import math
    from io import StringIO

    def _fmt(v) -> str:
        """
        Convierte un valor Python al formato que espera el protocolo COPY de PostgreSQL.
        - None, float NaN, pd.NA  → \\N  (NULL)
        - float sin decimales (8474564.0) → "8474564"  (evita error en columnas INTEGER)
        - resto → str(v)
        """
        if v is None:
            return "\\N"
        try:
            import pandas as _pd
            if v is _pd.NA:
                return "\\N"
        except Exception:
            pass
        if isinstance(v, float):
            if math.isnan(v):
                return "\\N"
            if v == int(v):          # entero representado como float (ej: 8474564.0)
                return str(int(v))
        return str(v)

    # Acceder a la conexión psycopg2 subyacente
    dbapi_conn = conn.connection

    with dbapi_conn.cursor() as cur:
        buf = StringIO()
        buf.write(
            "\n".join(
                "\t".join(_fmt(v) for v in row)
                for row in data_iter
            )
        )
        buf.seek(0)
        cur.copy_from(buf, table.name, sep="\t", null="\\N", columns=keys)


# ── Funciones de carga ────────────────────────────────────────────────────────

def _load_table(
    df: pd.DataFrame,
    table_name: str,
    engine,
    if_exists: str = "replace",
    chunksize: int | None = CHUNK_SIZE,
) -> None:
    """
    Carga un DataFrame en una tabla de PostgreSQL usando pandas to_sql()
    con el método COPY de Postgres para máxima velocidad.

    Parámetros
    ----------
    df         : DataFrame a cargar
    table_name : nombre de la tabla destino en Postgres
    engine     : Engine de SQLAlchemy (conexión a la DB)
    if_exists  : qué hacer si la tabla ya tiene datos:
                   'replace' → borra todos los registros existentes y carga de nuevo
                   'append'  → agrega filas sin borrar las anteriores
                   'fail'    → lanza error si ya hay datos
    chunksize  : cuántas filas procesar por lote. Default: CHUNK_SIZE (50.000).
                 Aplica a todas las tablas para evitar el problema de un único
                 INSERT gigante que traba a Postgres.
    """
    logger.info(f"Cargando '{table_name}': {len(df):,} filas...")

    df.to_sql(
        name=table_name,
        con=engine,
        if_exists=if_exists,
        index=False,             # No guardar el índice de pandas como columna
        chunksize=chunksize,     # Tamaño del lote — ahora aplica a todas las tablas
        method=_copy_method,     # COPY nativo de Postgres — 5-10x más rápido que INSERT
    )

    logger.info(f"  → '{table_name}' cargada ✓")


def load_shots_streaming(engine, src_hist=None, src_2022=None, chunksize: int = CHUNK_SIZE, on_chunk=None) -> None:
    """
    Carga la tabla de tiros leyendo los CSV **en chunks** para evitar OOM.

    En vez de cargar los ~1.6M filas a RAM de golpe, lee, transforma
    y carga bloques de `chunksize` filas secuencialmente, manteniendo
    el uso de memoria acotado (~200-400 MB en vez de varios GB).

    Flujo:
      1. TRUNCATE de la tabla shots
      2. Para cada chunk de shots_2007-2021.csv → transform → COPY a Postgres
      3. Para cada chunk de shots_2022.csv      → transform → COPY a Postgres

    Parámetros
    ----------
    engine    : Engine de SQLAlchemy conectado a la DB
    src_hist  : ruta al CSV histórico (str/Path) o None para usar data/raw/
    src_2022  : ruta al CSV 2022 (str/Path) o None para usar data/raw/
    chunksize : filas por chunk (default: CHUNK_SIZE = 20.000)
    """
    import os as _os
    from pipeline.extract import RAW_DATA_DIR, FILES, SHOTS_DTYPES
    from pipeline.transform import transform_shots_chunk

    if src_hist is None:
        src_hist = _os.path.join(RAW_DATA_DIR, FILES["shots_historical"])
    if src_2022 is None:
        src_2022 = _os.path.join(RAW_DATA_DIR, FILES["shots_2022"])

    logger.info("Truncando tabla shots para recarga completa...")
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE shots"))
        conn.commit()

    total_rows = 0
    chunk_num_global = 0
    for label, src in [("shots_historical", src_hist), ("shots_2022", src_2022)]:
        logger.info(f"Cargando {label} en chunks de {chunksize:,}...")
        for chunk in pd.read_csv(src, dtype=SHOTS_DTYPES, low_memory=False, chunksize=chunksize):
            chunk_num_global += 1
            transformed = transform_shots_chunk(chunk)
            del chunk
            if transformed.empty:
                continue
            transformed.to_sql(
                name="shots",
                con=engine,
                if_exists="append",
                index=False,
                chunksize=chunksize,
                method=_copy_method,
            )
            total_rows += len(transformed)
            del transformed
            logger.info(f"  → Chunk {chunk_num_global} | acumulado: {total_rows:,} filas")
            if on_chunk:
                on_chunk(chunk_num_global, total_rows)

    logger.info(f"Shots cargados: {total_rows:,} filas totales ✓")


def load_shots(df_shots: pd.DataFrame, engine) -> None:
    """
    Carga la tabla de tiros en PostgreSQL en lotes de CHUNK_SIZE filas.
    (Interfaz original — usa load_shots_streaming internamente si el DataFrame
    se pasa directamente. Para archivos grandes, preferir load_shots_streaming.)

    Parámetros
    ----------
    df_shots : DataFrame de tiros (output de transform.transform_shots)
    engine   : Engine de SQLAlchemy
    """
    logger.info(f"Iniciando carga de shots ({len(df_shots):,} filas en lotes de {CHUNK_SIZE:,})...")
    _load_table(df_shots, "shots", engine, if_exists="replace", chunksize=CHUNK_SIZE)


def load_teams(df_teams: pd.DataFrame, engine) -> None:
    """
    Carga la tabla de estadísticas por equipo.

    Al ser un dataset más pequeño no necesita lotes.
    Usamos if_exists='replace' para reemplazar datos viejos en cada carga.

    Parámetros
    ----------
    df_teams : DataFrame de equipos (output de transform.transform_teams)
    engine   : Engine de SQLAlchemy
    """
    _load_table(df_teams, "teams", engine, if_exists="replace")


def load_players(df_players: pd.DataFrame, engine) -> None:
    """
    Carga la tabla de jugadores.

    Dataset muy pequeño (~3K filas), carga directa sin lotes.

    Parámetros
    ----------
    df_players : DataFrame de jugadores (output de transform.transform_players)
    engine     : Engine de SQLAlchemy
    """
    _load_table(df_players, "players", engine, if_exists="replace")


# ── Función principal ─────────────────────────────────────────────────────────

def load_all(data: dict) -> None:
    """
    Ejecuta la carga completa del pipeline: conecta a Postgres, crea las
    tablas y carga los tres DataFrames.

    Parámetros
    ----------
    data : dict con claves 'shots', 'teams', 'players'
           (output de transform.transform_all())
           La clave 'shots' puede ser un DataFrame O None; si es None se
           usa load_shots_streaming con los archivos en data/raw/.

    El flujo es:
      1. get_engine()            → abre la configuración de conexión
      2. create_tables()         → crea las tablas si no existen (idempotente)
      3. load_shots_streaming()  → carga ~1.7M filas chunk a chunk (sin OOM)
      4. load_teams()            → carga equipos
      5. load_players()          → carga jugadores
    """
    logger.info("=== Iniciando carga en PostgreSQL ===")

    try:
        engine = get_engine()
        create_tables(engine)

        load_shots_streaming(engine)
        create_indexes(engine)   # después de la carga — más rápido que durante el COPY

        load_teams(data["teams"], engine)
        load_players(data["players"], engine)

        logger.info("=== Carga completa ✓ ===")

    except SQLAlchemyError as e:
        logger.error(f"Error durante la carga en PostgreSQL: {e}")
        raise


# ── Ejecución directa (para pruebas) ──────────────────────────────────────────
if __name__ == "__main__":
    """
    Permite correr el pipeline ETL completo desde la línea de comandos:
      python -m pipeline.load

    Esto ejecuta extract → transform → load de punta a punta.
    Útil para cargar los datos inicialmente o para recargar después
    de un cambio en la lógica de transformación.
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from pipeline.extract import extract_all
    from pipeline.transform import transform_all

    raw         = extract_all()
    transformed = transform_all(raw)
    load_all(transformed)