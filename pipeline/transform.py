"""
transform.py
------------
Segunda etapa del pipeline ETL de IceStats.
Limpia, valida y enriquece los DataFrames extraídos para su carga en PostgreSQL.

Transformaciones principales:
  - Shots : concat histórico + 2022, filtrado de errores, selección de columnas,
            y generación de columnas derivadas (gameSituation, dangerZone, isClutchSituation)
  - Teams : limpieza básica de duplicados y nulos
  - Players: limpieza de duplicados y valores faltantes
"""

import logging
import numpy as np
import pandas as pd

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Columnas a conservar del dataset de tiros ─────────────────────────────────
# De las 124 columnas originales se conservan sólo las necesarias para los
# tres módulos del dashboard (Directivo, Entrenador, Reclutador).
SHOTS_COLS_KEEP = [
    # Identificadores
    "shotID", "season", "isPlayoffGame", "game_id",
    # Tiempo y período
    "time", "period",
    # Equipos
    "homeTeamCode", "awayTeamCode", "team", "isHomeTeam", "homeTeamWon",
    # Marcador en el momento del tiro
    "homeTeamGoals", "awayTeamGoals",
    # Métricas esperadas (xGoal, etc.)
    "goal", "xGoal", "xFroze", "xRebound", "xShotWasOnGoal",
    # Ubicación del tiro (coordenadas ajustadas por arena)
    "xCordAdjusted", "yCordAdjusted", "arenaAdjustedShotDistance", "shotAngle",
    # Características del disparo
    "shotType", "shotWasOnGoal", "shotOnEmptyNet",
    "shotRebound", "shotRush", "shotGeneratedRebound",
    # Situación numérica (patinadores en cancha)
    "homeSkatersOnIce", "awaySkatersOnIce", "homeEmptyNet", "awayEmptyNet",
    # Jugadores involucrados
    "shooterPlayerId", "shooterName",
    "goalieIdForShot", "goalieNameForShot",
    "playerPositionThatDidEvent",
]

# Columnas que no pueden ser nulas en un tiro válido
CRITICAL_COLS = [
    "shotID", "season", "game_id",
    "xGoal", "xCordAdjusted", "yCordAdjusted",
    "shooterPlayerId",
]

# Columnas clave de la tabla de equipos
TEAMS_KEY_COLS = ["season", "team", "situation"]


# ── Funciones de derivación ───────────────────────────────────────────────────

def _derive_game_situation(df: pd.DataFrame) -> pd.Series:
    """
    Deriva la situación de juego para cada tiro:
      '5v5'  → igualdad numérica (5 vs 5)
      'PP'   → power play para el equipo que tira (ventaja numérica)
      'PK'   → penalty kill para el equipo que tira (inferioridad numérica)
      'EN'   → red vacía del equipo defensor
      'other'→ otras situaciones (4v4, 3v3, etc.)

    Necesario para RF-E02 (xGoals por situación) y RF-D01/D02 (Corsi/Fenwick).
    """
    home      = df["homeSkatersOnIce"]
    away      = df["awaySkatersOnIce"]
    is_home   = df["isHomeTeam"].astype(bool)
    home_empty = df["homeEmptyNet"].astype(bool)
    away_empty = df["awayEmptyNet"].astype(bool)

    # Red vacía del equipo defensor
    empty_net = (is_home & away_empty) | (~is_home & home_empty)

    # Patinadores del equipo que tira y del que defiende
    shooters_on  = home.where(is_home, away)   # home si tira home, else away
    defenders_on = away.where(is_home, home)   # away si tira home, else home

    conditions = [
        empty_net,
        (shooters_on == 5) & (defenders_on == 5),
        shooters_on > defenders_on,
        shooters_on < defenders_on,
    ]
    choices = ["EN", "5v5", "PP", "PK"]

    return pd.Series(
        np.select(conditions, choices, default="other"),
        index=df.index,
        name="gameSituation",
    )


def _derive_danger_zone(df: pd.DataFrame) -> pd.Series:
    """
    Clasifica cada tiro por zona de peligro según la distancia al arco:
      'high'   → < 20 pies  (zona de slot — mayor probabilidad de gol)
      'medium' → 20–40 pies
      'low'    → > 40 pies

    Necesario para el mapa de calor del Entrenador (RF-E01).
    """
    dist = df["arenaAdjustedShotDistance"]
    return pd.cut(
        dist,
        bins=[-1, 20, 40, float("inf")],
        labels=["high", "medium", "low"],
    ).rename("dangerZone")


def _derive_clutch_situation(df: pd.DataFrame) -> pd.Series:
    """
    Marca como True los tiros en situaciones de alta presión ('clutch'):
      - Partido de playoff, O
      - Tiempo suplementario (período > 3), O
      - Tercer período con diferencia de goles <= 1

    Necesario para la identificación de jugadores clutch (RF-R04).
    """
    goal_diff = (df["homeTeamGoals"] - df["awayTeamGoals"]).abs()
    is_clutch = (
        (df["isPlayoffGame"] == 1)
        | (df["period"] > 3)
        | ((df["period"] == 3) & (goal_diff <= 1))
    )
    return is_clutch.rename("isClutchSituation")


# ── Transformaciones por tabla ────────────────────────────────────────────────

def transform_shots(df_hist: pd.DataFrame, df_2022: pd.DataFrame) -> pd.DataFrame:
    """
    Combina y limpia los datasets de tiros (histórico + 2022).

    Pasos:
      1. Concatenar ambos DataFrames
      2. Eliminar filas duplicadas por shotID
      3. Filtrar valores de time == 999 (error conocido de MoneyPuck — Riesgo 1)
      4. Descartar filas con nulos en columnas críticas
      5. Seleccionar sólo las columnas relevantes (de 124 → ~37)
      6. Agregar columnas derivadas: gameSituation, dangerZone, isClutchSituation
    """
    logger.info("Transformando shots...")

    # 1. Concatenar
    df = pd.concat([df_hist, df_2022], ignore_index=True)
    logger.info(f"  → Tras concat: {len(df):,} filas")

    # 2. Eliminar duplicados por shotID
    before = len(df)
    df = df.drop_duplicates(subset="shotID")
    dropped = before - len(df)
    if dropped:
        logger.warning(f"  → {dropped:,} filas duplicadas eliminadas (shotID repetido)")
    else:
        logger.info("  → Sin duplicados detectados ✓")

    # 3. Filtrar time == 999 (variable temporal errónea — documentado por MoneyPuck)
    before = len(df)
    df = df[df["time"] != 999]
    dropped = before - len(df)
    if dropped:
        logger.info(f"  → {dropped:,} filas con time=999 descartadas")

    # 4. Descartar nulos en columnas críticas
    existing_critical = [c for c in CRITICAL_COLS if c in df.columns]
    before = len(df)
    df = df.dropna(subset=existing_critical)
    dropped = before - len(df)
    if dropped:
        logger.info(f"  → {dropped:,} filas con nulos en columnas críticas descartadas")

    # 5. Seleccionar columnas (ignorar las que no estén en el CSV)
    existing_cols = [c for c in SHOTS_COLS_KEEP if c in df.columns]
    missing = set(SHOTS_COLS_KEEP) - set(existing_cols)
    if missing:
        logger.warning(f"  → Columnas no encontradas en el CSV: {sorted(missing)}")
    df = df[existing_cols].copy()

    # 6. Columnas derivadas
    df["gameSituation"]    = _derive_game_situation(df)
    df["dangerZone"]       = _derive_danger_zone(df)
    df["isClutchSituation"] = _derive_clutch_situation(df)

    logger.info(f"  → Resultado final: {len(df):,} filas | {df.shape[1]} columnas")
    return df


def transform_teams(df_teams: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia el dataset de estadísticas por equipo (all_teams.csv).

    Pasos:
      1. Eliminar filas completamente duplicadas
      2. Descartar filas con nulos en columnas clave (season, team, situation)
    """
    logger.info("Transformando teams...")

    before = len(df_teams)
    df = df_teams.drop_duplicates()
    if len(df) < before:
        logger.warning(f"  → {before - len(df):,} filas duplicadas eliminadas en teams")

    existing_key = [c for c in TEAMS_KEY_COLS if c in df.columns]
    df = df.dropna(subset=existing_key).copy()

    logger.info(f"  → Resultado: {len(df):,} filas | {df.shape[1]} columnas")
    return df


def transform_players(df_players: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia el dataset de jugadores (allPlayersLookup.csv).

    Pasos:
      1. Eliminar duplicados por playerId
      2. Rellenar posición desconocida con 'Unknown'
    """
    logger.info("Transformando players...")

    id_col = "playerId" if "playerId" in df_players.columns else df_players.columns[0]
    before = len(df_players)
    df = df_players.drop_duplicates(subset=id_col).copy()
    if len(df) < before:
        logger.warning(f"  → {before - len(df):,} jugadores duplicados eliminados")

    if "position" in df.columns:
        df["position"] = df["position"].fillna("Unknown")

    logger.info(f"  → Resultado: {len(df):,} filas | {df.shape[1]} columnas")
    return df


# ── Validación de integridad ──────────────────────────────────────────────────

def validate_player_ids(df_shots: pd.DataFrame, df_players: pd.DataFrame) -> None:
    """
    Verifica que los IDs de jugadores en la tabla de tiros existan en la tabla
    de jugadores. Emite advertencias sin interrumpir el pipeline (Riesgo 4).
    """
    if "playerId" not in df_players.columns:
        logger.warning("Columna 'playerId' no encontrada en players — se omite validación de IDs")
        return

    known_ids = set(df_players["playerId"].dropna().astype(int))

    for col, label in [("shooterPlayerId", "shooterPlayerId"), ("goalieIdForShot", "goalieIdForShot")]:
        if col not in df_shots.columns:
            continue
        ids = set(df_shots[col].dropna().astype(int))
        missing = ids - known_ids
        if missing:
            logger.warning(
                f"  → {len(missing):,} {label} sin match en players "
                f"(ejemplos: {sorted(list(missing))[:5]})"
            )
        else:
            logger.info(f"  → Todos los {label} tienen match en players ✓")


# ── Función principal ─────────────────────────────────────────────────────────

def transform_all(data: dict) -> dict:
    """
    Ejecuta la transformación completa del pipeline.

    Parámetros
    ----------
    data : dict con claves 'shots_historical', 'shots_2022', 'teams', 'players'
           (output de extract.extract_all())

    Retorna
    -------
    dict con claves 'shots', 'teams', 'players' listos para cargar en PostgreSQL
    """
    logger.info("=== Iniciando transformación ===")

    shots   = transform_shots(data["shots_historical"], data["shots_2022"])
    teams   = transform_teams(data["teams"])
    players = transform_players(data["players"])

    logger.info("Validando integridad de IDs de jugadores...")
    validate_player_ids(shots, players)

    logger.info("=== Transformación completa ===")
    return {
        "shots":   shots,
        "teams":   teams,
        "players": players,
    }


# ── Ejecución directa (para pruebas) ──────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from extract import extract_all

    raw = extract_all()
    transformed = transform_all(raw)

    print("\nResumen de DataFrames transformados:")
    for nombre, df in transformed.items():
        print(f"  {nombre:10s} → {len(df):>10,} filas  |  {df.shape[1]:>3} columnas")
        if nombre == "shots":
            print(f"             Columnas derivadas: gameSituation, dangerZone, isClutchSituation")
            print(f"             Distribución gameSituation:\n{df['gameSituation'].value_counts().to_string()}")
