"""
extract.py
----------
Primera etapa del pipeline ETL de IceStats.

Soporta dos modos de operación:

  Modo archivo local (desarrollo / ejecución desde consola)
  ─────────────────────────────────────────────────────────
  Lee los CSV desde data/raw/. Se usa cuando no se proveen archivos externos.

      from pipeline.extract import extract_all
      data = extract_all()

  Modo upload (dashboard Streamlit)
  ──────────────────────────────────
  Acepta objetos file-like devueltos por st.file_uploader. Cada función
  de extracción recibe un parámetro `source` que puede ser:
    - None          → lee desde data/raw/ usando el nombre de archivo por defecto
    - str / Path    → ruta explícita al archivo en disco
    - file-like obj → objeto en memoria (UploadedFile de Streamlit, BytesIO, etc.)

  Uso típico desde app.py:

      uploaded = {
          "shots_historical": st.file_uploader("shots 2007-2021"),
          "shots_2022":       st.file_uploader("shots 2022"),
          "teams":            st.file_uploader("equipos"),
          "players":          st.file_uploader("jugadores"),
      }
      if all(uploaded.values()):
          data = extract_all(uploaded_files=uploaded)
"""

import os
import logging
from typing import Union, IO, Optional

import pandas as pd

# ── Configuración de logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Rutas (modo archivo local) ─────────────────────────────────────────────────
# Directorio base del proyecto (un nivel arriba de /pipeline)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")

# Nombres de archivos esperados en data/raw/ (usados solo en modo local)
FILES = {
    "shots_historical": "shots_2007-2021.csv",
    "shots_2022":       "shots_2022.csv",
    "teams":            "all_teams.csv",
    "players":          "allPlayersLookup.csv",
}

# Tipo para el parámetro source de cada función de extracción
Source = Optional[Union[str, os.PathLike, IO]]

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


# ── Helpers internos ──────────────────────────────────────────────────────────

def _build_path(filename: str) -> str:
    """
    Construye la ruta completa a un archivo en data/raw/ y valida que exista.
    Solo se usa en modo archivo local (cuando source=None).
    """
    path = os.path.join(RAW_DATA_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No se encontró el archivo '{filename}' en '{RAW_DATA_DIR}'.\n"
            f"Asegurate de copiar los CSV a la carpeta data/raw/ antes de correr el pipeline.\n"
            f"Alternativamente, usá extract_all(uploaded_files={{...}}) para pasar los archivos directamente."
        )
    return path


def _resolve_source(source: Source, file_key: str) -> Union[str, IO]:
    """
    Resuelve el origen del archivo para pd.read_csv().

    Parámetros
    ----------
    source   : None, ruta (str/Path) o file-like object
    file_key : clave en FILES (e.g. 'shots_historical'), usada solo si source es None

    Retorna
    -------
    Un valor que pd.read_csv() acepta directamente como primer argumento.
    """
    if source is None:
        return _build_path(FILES[file_key])
    return source  # str, Path o file-like: pd.read_csv los acepta a todos


# ── Funciones de extracción ────────────────────────────────────────────────────

def extract_shots_historical(source: Source = None) -> pd.DataFrame:
    """
    Lee el dataset histórico de tiros (~1.6M filas, temporadas 2007-2021).
    Aplica dtypes optimizados para reducir el uso de memoria.

    Parámetros
    ----------
    source : None | str | Path | file-like (UploadedFile de Streamlit, BytesIO, etc.)
        - None   → lee shots_2007-2021.csv desde data/raw/
        - otros  → usa el objeto o ruta proporcionados directamente
    """
    src = _resolve_source(source, "shots_historical")
    label = FILES["shots_historical"] if source is None else getattr(source, "name", "archivo subido")
    logger.info(f"Leyendo {label}...")

    df = pd.read_csv(src, dtype=SHOTS_DTYPES, low_memory=False)

    logger.info(f"  → {len(df):,} filas | {df.shape[1]} columnas | "
                f"{df.memory_usage(deep=True).sum() / 1e6:.1f} MB en memoria")
    return df


def extract_shots_2022(source: Source = None) -> pd.DataFrame:
    """
    Lee el dataset de tiros de la temporada 2022 (~122K filas).
    Misma estructura que el histórico pero con columnas en orden alfabético.

    Parámetros
    ----------
    source : None | str | Path | file-like (UploadedFile de Streamlit, BytesIO, etc.)
        - None   → lee shots_2022.csv desde data/raw/
        - otros  → usa el objeto o ruta proporcionados directamente
    """
    src = _resolve_source(source, "shots_2022")
    label = FILES["shots_2022"] if source is None else getattr(source, "name", "archivo subido")
    logger.info(f"Leyendo {label}...")

    df = pd.read_csv(src, dtype=SHOTS_DTYPES, low_memory=False)

    logger.info(f"  → {len(df):,} filas | {df.shape[1]} columnas | "
                f"{df.memory_usage(deep=True).sum() / 1e6:.1f} MB en memoria")
    return df


def extract_teams(source: Source = None) -> pd.DataFrame:
    """
    Lee el dataset de estadísticas por equipo (~190K filas).
    Incluye métricas agregadas por equipo, temporada y situación de juego.

    Parámetros
    ----------
    source : None | str | Path | file-like (UploadedFile de Streamlit, BytesIO, etc.)
        - None   → lee all_teams.csv desde data/raw/
        - otros  → usa el objeto o ruta proporcionados directamente
    """
    src = _resolve_source(source, "teams")
    label = FILES["teams"] if source is None else getattr(source, "name", "archivo subido")
    logger.info(f"Leyendo {label}...")

    df = pd.read_csv(src, low_memory=False)

    logger.info(f"  → {len(df):,} filas | {df.shape[1]} columnas")
    return df


def extract_players(source: Source = None) -> pd.DataFrame:
    """
    Lee el dataset de jugadores (~3K filas).
    Contiene datos personales: nombre, posición, equipo, etc.

    Parámetros
    ----------
    source : None | str | Path | file-like (UploadedFile de Streamlit, BytesIO, etc.)
        - None   → lee allPlayersLookup.csv desde data/raw/
        - otros  → usa el objeto o ruta proporcionados directamente
    """
    src = _resolve_source(source, "players")
    label = FILES["players"] if source is None else getattr(source, "name", "archivo subido")
    logger.info(f"Leyendo {label}...")

    df = pd.read_csv(src, low_memory=False)

    logger.info(f"  → {len(df):,} filas | {df.shape[1]} columnas")
    return df


def extract_all(uploaded_files: Optional[dict] = None) -> dict[str, pd.DataFrame]:
    """
    Ejecuta la extracción completa de todos los archivos.

    Parámetros
    ----------
    uploaded_files : dict | None
        Diccionario con los archivos subidos por el usuario desde la UI.
        Las claves válidas son:
          - 'shots_historical' : archivo de tiros 2007-2021
          - 'shots_2022'       : archivo de tiros 2022
          - 'teams'            : archivo de equipos
          - 'players'          : archivo de jugadores

        Cada valor puede ser un UploadedFile de Streamlit, un BytesIO,
        o cualquier file-like object aceptado por pd.read_csv().

        Si una clave no está presente o su valor es None, se intenta
        leer el archivo correspondiente desde data/raw/ (modo local).

        Si uploaded_files es None por completo, todos los archivos
        se leen desde data/raw/ (comportamiento original).

    Retorna
    -------
    dict con claves: 'shots_historical', 'shots_2022', 'teams', 'players'
    Cada valor es un DataFrame listo para pasar a transform.transform_all().

    Ejemplos
    --------
    # Modo local (desarrollo / consola):
    data = extract_all()

    # Modo upload (dashboard Streamlit):
    data = extract_all(uploaded_files={
        "shots_historical": st.session_state["file_hist"],
        "shots_2022":       st.session_state["file_2022"],
        "teams":            st.session_state["file_teams"],
        "players":          st.session_state["file_players"],
    })
    """
    uf = uploaded_files or {}

    if uf:
        logger.info("=== Iniciando extracción (modo upload) ===")
    else:
        logger.info("=== Iniciando extracción (modo local) ===")
        logger.info(f"Directorio de datos: {RAW_DATA_DIR}")

    data = {
        "shots_historical": extract_shots_historical(uf.get("shots_historical")),
        "shots_2022":       extract_shots_2022(uf.get("shots_2022")),
        "teams":            extract_teams(uf.get("teams")),
        "players":          extract_players(uf.get("players")),
    }

    logger.info("=== Extracción completa ===")
    return data


# ── Ejecución directa (para pruebas en modo local) ────────────────────────────
if __name__ == "__main__":
    dataframes = extract_all()
    print("\nResumen de DataFrames extraídos:")
    for nombre, df in dataframes.items():
        print(f"  {nombre:20s} → {len(df):>10,} filas  |  {df.shape[1]:>3} columnas")
