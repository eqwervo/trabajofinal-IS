# IceStats — Sistema de Análisis de Estadísticas NHL

Dashboard interactivo para el análisis de estadísticas avanzadas de la NHL, orientado a tres perfiles de usuario: Directivos, Entrenadores y Reclutadores.

## Stack

- **Frontend:** Streamlit
- **Base de datos:** PostgreSQL 15
- **ETL:** Python (pandas, SQLAlchemy, psycopg2)
- **Visualizaciones:** Plotly
- **Contenedores:** Docker + Docker Compose

## Estructura del proyecto

```
trabajofinal-IS/
├── dashboard/
│   └── app.py              # Aplicación Streamlit (UI + inicialización)
├── pipeline/
│   ├── extract.py          # Extracción de archivos CSV
│   ├── transform.py        # Limpieza, validación y columnas derivadas
│   └── load.py             # Carga en PostgreSQL (streaming por chunks)
├── data/
│   └── raw/                # Datasets CSV de MoneyPuck
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Dataset requerido (MoneyPuck)

Colocar los siguientes archivos en `data/raw/` antes de iniciar:

| Archivo | Descripción |
|---|---|
| `shots_2007-2021.csv` | Datos históricos de disparos (temporadas 2007–2021) |
| `shots_2022.csv` | Disparos de la temporada 2022 |
| `all_teams.csv` | Estadísticas agregadas por equipo, temporada y situación |
| `allPlayersLookup.csv` | Perfil de jugadores (nombre, posición, nacionalidad, datos físicos) |

## Inicio rápido

```bash
# 1. Clonar el repositorio y agregar los CSV en data/raw/

# 2. Levantar los contenedores
docker compose up --build

# 3. Acceder al dashboard
# http://localhost:8501
```

Al iniciar, el sistema detecta automáticamente si la base de datos está vacía y ejecuta el pipeline ETL completo (extracción → transformación → carga en PostgreSQL).

## Pipeline ETL

- Los archivos de disparos se procesan en **chunks de 20.000 filas** para evitar agotamiento de memoria con datasets de ~1,6 M de filas.
- Los índices de PostgreSQL se crean **después de la carga** para mayor velocidad.
- Las tablas `teams` y `players` se crean con todos sus campos mediante inferencia automática de pandas.

## Actualización de datos

El dashboard incluye una sección para cargar nuevos archivos CSV de disparos directamente desde la interfaz, sin necesidad de acceder al servidor.

## Variables de entorno

| Variable | Valor por defecto |
|---|---|
| `DATABASE_URL` | `postgresql://icestats:icestats@db:5432/icestats` |
