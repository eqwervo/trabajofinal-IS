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
CHUNK_SIZE = 50_000


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
    -- Identificadores únicos
    "shotID"               INTEGER PRIMARY KEY,
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

TEAMS_DDL = """
CREATE TABLE IF NOT EXISTS teams (
    -- Clave compuesta: un equipo puede aparecer en múltiples temporadas y situaciones
    "season"       SMALLINT,
    "team"         VARCHAR(10),
    "situation"    VARCHAR(20),
    PRIMARY KEY ("season", "team", "situation")
);
"""

PLAYERS_DDL = """
CREATE TABLE IF NOT EXISTS players (
    "playerId"   INTEGER PRIMARY KEY,
    "name"       VARCHAR(100),
    "position"   VARCHAR(20)
);
"""


def create_tables(engine) -> None:
    """
    Crea las tablas en PostgreSQL si todavía no existen.

    Usa un context manager (with engine.connect() as conn) para garantizar
    que la conexión se cierre automáticamente al terminar, incluso si hay
    un error. Esto evita "connection leaks" (conexiones abiertas sin usar).

    text() convierte el string SQL en un objeto que SQLAlchemy puede ejecutar.
    conn.commit() confirma la transacción — sin esto, PostgreSQL no guarda
    los cambios (DDL en Postgres requiere commit explícito en SQLAlchemy 2.x).
    """
    logger.info("Creando tablas si no existen...")
    with engine.connect() as conn:
        conn.execute(text(SHOTS_DDL))
        conn.execute(text(TEAMS_DDL))
        conn.execute(text(PLAYERS_DDL))
        conn.commit()
    logger.info("Tablas verificadas ✓")


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
    from io import StringIO

    # Acceder a la conexión psycopg2 subyacente
    dbapi_conn = conn.connection

    with dbapi_conn.cursor() as cur:
        buf = StringIO()
        # Serializar filas: None → \N (NULL en COPY), resto → string con tab como separador
        buf.write(
            "\n".join(
                "\t".join(
                    "\\N" if v is None else str(v)
                    for v in row
                )
                for row in data_iter
            )
        )
        buf.seek(0)  # Volver al inicio del buffer para que COPY lo lea desde el principio
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


def load_shots(df_shots: pd.DataFrame, engine) -> None:
    """
    Carga la tabla de tiros en PostgreSQL en lotes de CHUNK_SIZE filas.

    ¿Por qué en lotes?
      El dataset de tiros tiene ~1.7 millones de filas. Si intentamos
      insertar todo de una vez, Python construiría una única sentencia SQL
      gigante que podría:
        - Agotar la memoria RAM disponible
        - Superar el límite de tamaño de paquete de red del servidor
        - Hacer que la conexión se corte por timeout

      Al dividir en lotes de 50.000 filas, cada INSERT es manejable y
      podemos ver el progreso en los logs.

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

    Esta es la función que llama el orquestador del pipeline (o el dashboard).

    Parámetros
    ----------
    data : dict con claves 'shots', 'teams', 'players'
           (output de transform.transform_all())

    El flujo es:
      1. get_engine()     → abre la configuración de conexión
      2. create_tables()  → crea las tablas si no existen (idempotente)
      3. load_shots()     → carga ~1.7M filas en lotes
      4. load_teams()     → carga equipos
      5. load_players()   → carga jugadores

    Si cualquier paso falla, SQLAlchemyError captura el error y lo loggea
    con detalle para facilitar el debugging.
    """
    logger.info("=== Iniciando carga en PostgreSQL ===")

    try:
        # Paso 1: Crear el motor de conexión
        engine = get_engine()

        # Paso 2: Crear tablas si no existen
        create_tables(engine)

        # Paso 3-5: Cargar cada tabla
        load_shots(data["shots"], engine)
        load_teams(data["teams"], engine)
        load_players(data["players"], engine)

        logger.info("=== Carga completa ✓ ===")

    except SQLAlchemyError as e:
        # SQLAlchemyError es la clase base de todos los errores de SQLAlchemy.
        # Capturarla acá nos permite dar un mensaje claro y no crashear el
        # pipeline completo si hay un problema de conexión o de datos.
        logger.error(f"Error durante la carga en PostgreSQL: {e}")
        raise  # Re-lanzamos para que el llamador sepa que algo falló


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
