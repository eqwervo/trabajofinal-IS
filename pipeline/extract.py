"""
extract.py
----------
Primera etapa del pipeline ETL de IceStats.
Lee los archivos CSV crudos desde data/raw/ y los retorna como DataFrames de pandas.
"""

import os
import logging
import pandas as pd

# ── Configuración de logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Rutas ─────────────────────────────────────────────────────────────────────
# Directorio base del proyecto (un nivel arriba de /pipeline)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")

# Nombres de archivos esperados
FILES = {
    "shots_historical": "shots_2007-2021.csv",
    "shots_2022":       "shots_2022.csv",
    "teams":            "all_teams.csv",
    "players":          "allPlayersLookup.csv",
}

# ── Tipos de datos optimizados para el archivo de tiros ───────────────────────
# Definir dtypes explícitos reduce el uso de memoria y acelera la lectura.
SHOTS_DTYPES = {
    "shotID":               "int32",
    "season":               "int16",
    "isPlayoffGame":        "int8",
    "game_id":              "int32",
    "homeTeamWon":          "int8",
    "time":                 "int16",
    "period":               "int8",
    "goal":                 "int8",
    "homeTeamGoals":        "int8",
    "awayTeamGoals":        "int8",
    "homeSkatersOnIce":     "int8",
    "awaySkatersOnIce":     "int8",
    "homeEmptyNet":         "int8",
    "awayEmptyNet":         "int8",
    "isHomeTeam":           "int8",
    "shotWasOnGoal":        "int8",
    "shotOnEmptyNet":       "int8",
    "shotRebound":          "int8",
    "shotRush":             "int8",
    "shotGeneratedRebound": "int8",
    "shotGoalieFroze":      "int8",
    "shotPlayStopped":      "int8",
}


# ── Funciones de extracción ────────────────────────────────────────────────────

def _build_path(filename: str) -> str:
    """Construye la ruta completa y valida que el archivo exista."""
    path = os.path.join(RAW_DATA_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No se encontró el archivo '{filename}' en '{RAW_DATA_DIR}'.\n"
            f"Asegurate de copiar los CSV a la carpeta data/raw/ antes de correr el pipeline."
        )
    return path


def extract_shots_historical() -> pd.DataFrame:
    """
    Lee shots_2007-2021.csv (~1.6M filas).
    Aplica dtypes optimizados para reducir el uso de memoria.
    """
    path = _build_path(FILES["shots_historical"])
    logger.info(f"Leyendo {FILES['shots_historical']}...")

    df = pd.read_csv(
        path,
        dtype=SHOTS_DTYPES,
        low_memory=False,
    )

    logger.info(f"  → {len(df):,} filas | {df.shape[1]} columnas | "
                f"{df.memory_usage(deep=True).sum() / 1e6:.1f} MB en memoria")
    return df


def extract_shots_2022() -> pd.DataFrame:
    """
    Lee shots_2022.csv (~122K filas).
    Misma estructura que el histórico pero con columnas en orden alfabético.
    """
    path = _build_path(FILES["shots_2022"])
    logger.info(f"Leyendo {FILES['shots_2022']}...")

    df = pd.read_csv(
        path,
        dtype=SHOTS_DTYPES,
        low_memory=False,
    )

    logger.info(f"  → {len(df):,} filas | {df.shape[1]} columnas | "
                f"{df.memory_usage(deep=True).sum() / 1e6:.1f} MB en memoria")
    return df


def extract_teams() -> pd.DataFrame:
    """
    Lee all_teams.csv (~190K filas).
    Estadísticas agregadas por equipo, temporada y situación de juego.
    """
    path = _build_path(FILES["teams"])
    logger.info(f"Leyendo {FILES['teams']}...")

    df = pd.read_csv(path, low_memory=False)

    logger.info(f"  → {len(df):,} filas | {df.shape[1]} columnas")
    return df


def extract_players() -> pd.DataFrame:
    """
    Lee allPlayersLookup.csv (~3K filas).
    Datos personales de jugadores: nombre, posición, equipo, etc.
    """
    path = _build_path(FILES["players"])
    logger.info(f"Leyendo {FILES['players']}...")

    df = pd.read_csv(path, low_memory=False)

    logger.info(f"  → {len(df):,} filas | {df.shape[1]} columnas")
    return df


def extract_all() -> dict[str, pd.DataFrame]:
    """
    Ejecuta la extracción completa de todos los archivos.

    Retorna
    -------
    dict con claves: 'shots_historical', 'shots_2022', 'teams', 'players'
    """
    logger.info("=== Iniciando extracción ===")
    logger.info(f"Directorio de datos: {RAW_DATA_DIR}")

    data = {
        "shots_historical": extract_shots_historical(),
        "shots_2022":       extract_shots_2022(),
        "teams":            extract_teams(),
        "players":          extract_players(),
    }

    logger.info("=== Extracción completa ===")
    return data


# ── Ejecución directa (para pruebas) ──────────────────────────────────────────
if __name__ == "__main__":
    dataframes = extract_all()
    print("\nResumen de DataFrames extraídos:")
    for nombre, df in dataframes.items():
        print(f"  {nombre:20s} → {len(df):>10,} filas  |  {df.shape[1]:>3} columnas")
