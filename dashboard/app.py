import os
import base64
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

def _logo_b64() -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

_LOGO = _logo_b64()

st.set_page_config(page_title="IceStats", layout="wide", initial_sidebar_state="collapsed")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;800&family=Exo+2:ital,wght@0,300;0,400;0,600;1,300&display=swap');

/* Fondo degradado animado */
.stApp {
    background: linear-gradient(125deg, #06001a 0%, #000c28 30%, #001a18 65%, #0a0012 100%);
    background-attachment: fixed;
}

/* Grid sutil */
.stApp::after {
    content: "";
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(79,195,247,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(79,195,247,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
}

/* Fuentes globales */
html, body, [class*="css"], .stMarkdown, p, span, label, div {
    font-family: 'Exo 2', sans-serif !important;
}

/* Títulos con gradiente */
h1, h2, h3 {
    font-family: 'Orbitron', monospace !important;
    background: linear-gradient(90deg, #4fc3f7 0%, #a78bfa 50%, #00e5ff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 4px !important;
    text-transform: uppercase;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(0,0,0,0.6) !important;
    border: 1px solid rgba(79,195,247,0.12) !important;
    border-radius: 14px !important;
    padding: 6px !important;
    gap: 8px !important;
    backdrop-filter: blur(20px) saturate(1.5);
    box-shadow: 0 4px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(79,195,247,0.08);
    width: fit-content !important;
    margin: 0 auto !important;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Orbitron', monospace !important;
    font-size: 0.62rem !important;
    font-weight: 700 !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    color: rgba(79,195,247,0.45) !important;
    border: 1px solid rgba(79,195,247,0.1) !important;
    border-radius: 10px !important;
    padding: 11px 30px !important;
    transition: all 0.35s cubic-bezier(0.4,0,0.2,1) !important;
    background: transparent !important;
    position: relative;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #4fc3f7 !important;
    border-color: rgba(79,195,247,0.5) !important;
    box-shadow: 0 0 20px rgba(79,195,247,0.2), inset 0 0 20px rgba(79,195,247,0.04) !important;
    background: rgba(79,195,247,0.04) !important;
    transform: translateY(-1px);
}

.stTabs [aria-selected="true"] {
    color: #03111a !important;
    background: linear-gradient(135deg, #4fc3f7 0%, #a78bfa 100%) !important;
    border-color: transparent !important;
    box-shadow: 0 0 30px rgba(79,195,247,0.7), 0 0 80px rgba(167,139,250,0.3), 0 4px 16px rgba(0,0,0,0.4) !important;
    font-weight: 800 !important;
    transform: translateY(-1px);
}

/* Métricas */
[data-testid="metric-container"] {
    background: rgba(6,0,26,0.7) !important;
    border: 1px solid rgba(79,195,247,0.18) !important;
    border-radius: 14px !important;
    padding: 20px 24px !important;
    transition: all 0.3s ease !important;
    backdrop-filter: blur(12px);
    position: relative;
    overflow: hidden;
}

[data-testid="metric-container"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #4fc3f7, #a78bfa, transparent);
}

[data-testid="metric-container"]::after {
    content: "";
    position: absolute;
    bottom: -40px; right: -40px;
    width: 80px; height: 80px;
    background: radial-gradient(circle, rgba(79,195,247,0.08) 0%, transparent 70%);
    border-radius: 50%;
}

[data-testid="metric-container"]:hover {
    border-color: rgba(79,195,247,0.45) !important;
    box-shadow: 0 0 30px rgba(79,195,247,0.18), 0 8px 40px rgba(0,0,0,0.5) !important;
    transform: translateY(-4px) !important;
}

[data-testid="metric-container"] label {
    font-family: 'Orbitron', monospace !important;
    font-size: 0.57rem !important;
    letter-spacing: 2.5px !important;
    text-transform: uppercase !important;
    color: rgba(79,195,247,0.65) !important;
}

[data-testid="metric-container"] [data-testid="metric-value"] {
    font-family: 'Orbitron', monospace !important;
    font-size: 1.7rem !important;
    font-weight: 800 !important;
    color: #e6edf3 !important;
}

/* Selectbox */
.stSelectbox > div > div {
    border: 1px solid rgba(79,195,247,0.25) !important;
    background: rgba(6,0,26,0.7) !important;
    border-radius: 10px !important;
    backdrop-filter: blur(8px);
}

/* Divider */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(79,195,247,0.35), rgba(167,139,250,0.35), transparent) !important;
    margin: 28px 0 !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(79,195,247,0.18) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* Animación entrada */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
}
.element-container { animation: fadeInUp 0.45s ease forwards; }

/* DB sync indicator */
.db-sync {
    text-align: right;
    flex-shrink: 0;
}
.db-sync-status {
    font-family: 'Exo 2', sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #66bb6a;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 7px;
}
.db-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #66bb6a;
    box-shadow: 0 0 8px #66bb6a;
    animation: pulse-dot 2.5s ease-in-out infinite;
    flex-shrink: 0;
}
@keyframes pulse-dot {
    0%,100% { opacity:1; box-shadow:0 0 8px #66bb6a; }
    50%      { opacity:0.55; box-shadow:0 0 16px #66bb6a, 0 0 4px #66bb6a; }
}
.db-sync-file {
    font-family: 'Exo 2', sans-serif;
    font-size: 0.68rem;
    color: rgba(79,195,247,0.65);
    margin-top: 5px;
    letter-spacing: 0.5px;
}
.db-sync-meta {
    font-family: 'Exo 2', sans-serif;
    font-size: 0.62rem;
    color: rgba(79,195,247,0.38);
    margin-top: 3px;
    letter-spacing: 0.5px;
}

/* Caption */
.stCaption {
    font-family: 'Exo 2', sans-serif !important;
    color: rgba(79,195,247,0.45) !important;
    letter-spacing: 1.5px !important;
    font-style: italic;
}

/* Section header */
.sh {
    font-family: 'Orbitron', monospace;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: rgba(79,195,247,0.75);
    border-left: 3px solid;
    border-image: linear-gradient(180deg, #4fc3f7, #a78bfa) 1;
    padding-left: 12px;
    margin: 20px 0 10px 0;
    text-shadow: 0 0 12px rgba(79,195,247,0.4);
}

/* Banner */
.banner {
    background: linear-gradient(135deg, rgba(79,195,247,0.06) 0%, rgba(167,139,250,0.08) 50%, rgba(0,229,255,0.04) 100%);
    border: 1px solid rgba(79,195,247,0.18);
    border-radius: 20px;
    padding: 28px 36px;
    margin-bottom: 28px;
    backdrop-filter: blur(20px) saturate(1.8);
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 60px rgba(79,195,247,0.06), inset 0 1px 0 rgba(255,255,255,0.04);
}

.banner::before {
    content: "";
    position: absolute;
    top: -60%; left: -20%;
    width: 80%; height: 220%;
    background: radial-gradient(ellipse, rgba(79,195,247,0.05) 0%, transparent 65%);
    animation: glow-pulse 5s ease-in-out infinite;
}

.banner::after {
    content: "";
    position: absolute;
    top: -60%; right: -20%;
    width: 60%; height: 220%;
    background: radial-gradient(ellipse, rgba(167,139,250,0.05) 0%, transparent 65%);
    animation: glow-pulse 5s ease-in-out infinite reverse;
}

@keyframes glow-pulse {
    0%,100% { opacity:0.6; transform:scale(1); }
    50%      { opacity:1;   transform:scale(1.08); }
}

.banner-title {
    font-family: 'Orbitron', monospace;
    font-size: 2.2rem;
    font-weight: 800;
    letter-spacing: 8px;
    background: linear-gradient(90deg, #4fc3f7 0%, #a78bfa 45%, #00e5ff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    position: relative; z-index: 1;
    text-shadow: none;
    filter: drop-shadow(0 0 20px rgba(79,195,247,0.3));
}

.banner-sub {
    font-family: 'Exo 2', sans-serif;
    font-size: 0.75rem;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: rgba(79,195,247,0.5);
    margin-top: 8px;
    position: relative; z-index: 1;
}

/* Spinner */
.stSpinner > div { border-top-color: #4fc3f7 !important; }

/* Footer de estado de BD */
.db-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(6,0,26,0.92);
    border-top: 1px solid rgba(79,195,247,0.18);
    padding: 8px 28px;
    display: flex;
    align-items: center;
    gap: 20px;
    backdrop-filter: blur(16px);
    z-index: 9999;
}
</style>
""", unsafe_allow_html=True)

# ── Constantes visuales ───────────────────────────────────────────────────────
BG       = "rgba(0,0,0,0)"
CHART_BG = "rgba(6,0,26,0.75)"
C_CYAN   = "#4fc3f7"
C_PURP   = "#a78bfa"
C_RED    = "#ef5350"
C_ORG    = "#ffa726"
C_GRN    = "#66bb6a"
FONT_H   = "Orbitron"
FONT_B   = "Exo 2"

def base_layout(fig, title="", height=None):
    upd = dict(
        template="plotly_dark",
        title=dict(text=title, font=dict(family=FONT_H, size=12, color=C_CYAN), x=0.01),
        paper_bgcolor=BG, plot_bgcolor=CHART_BG,
        font=dict(family=FONT_B, color="#c9d1d9"),
        margin=dict(l=16, r=16, t=44, b=16),
        xaxis=dict(gridcolor="rgba(79,195,247,0.06)", linecolor="rgba(79,195,247,0.15)"),
        yaxis=dict(gridcolor="rgba(79,195,247,0.06)", linecolor="rgba(79,195,247,0.15)"),
    )
    if height: upd["height"] = height
    fig.update_layout(**upd)
    return fig

def sh(label):
    st.markdown(f'<div class="sh">{label}</div>', unsafe_allow_html=True)

# ── DB ────────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_engine():
    url = os.getenv("DATABASE_URL", "postgresql://icestats:icestats@localhost:5432/icestats")
    return create_engine(url, pool_pre_ping=True)

@st.cache_data(ttl=3600)
def run_query(_engine, sql, params=None):
    with _engine.connect() as conn:
        res = conn.execute(text(sql), params or {})
        df  = pd.DataFrame(res.fetchall(), columns=list(res.keys()))
    # PostgreSQL NUMERIC/DECIMAL → Python Decimal → Plotly falla: convertir a float
    for col in df.select_dtypes(include=["object"]).columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass
    return df

engine = get_engine()

if "pipeline_checked" not in st.session_state:
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM shots")).scalar()
    except Exception:
        count = 0

    if count == 0:
        _, _mid, _ = st.columns([1, 1, 1])
        with _mid:
            if _LOGO:
                st.markdown(f'<img src="data:image/png;base64,{_LOGO}" style="width:100%;filter:drop-shadow(0 0 24px rgba(79,195,247,0.5));">', unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;font-family:Orbitron,monospace;color:#4fc3f7;letter-spacing:3px;font-size:0.8rem;margin-top:16px;'>INICIALIZANDO BASE DE DATOS</p>", unsafe_allow_html=True)
        with st.spinner("Esto puede tardar unos minutos..."):
            import sys
            sys.path.insert(0, "/app")
            from pipeline.extract import extract_all
            from pipeline.transform import transform_all
            from pipeline.load import load_all
            raw = extract_all()
            transformed = transform_all(raw)
            load_all(transformed)

    st.session_state["pipeline_checked"] = True

@st.cache_data(ttl=3600)
def load_globals(_engine):
    teams = run_query(_engine,
        'SELECT DISTINCT "homeTeamCode" AS t FROM shots '
        'UNION SELECT DISTINCT "awayTeamCode" FROM shots ORDER BY t'
    )["t"].tolist()
    seasons = sorted([int(r) for r in
        run_query(_engine, "SELECT DISTINCT season FROM shots ORDER BY season")["season"]])
    return teams, seasons

teams, seasons = load_globals(engine)

@st.cache_data(ttl=3600)
def load_db_stats(_engine):
    from datetime import date
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    try:
        from pipeline.extract import FILES as _FILES
        shot_files = " · ".join([_FILES["shots_historical"], _FILES["shots_2022"]])
    except Exception:
        shot_files = "shots_2007-2021.csv · shots_2022.csv"
    with _engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM shots")).scalar()
    meses = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    hoy = date.today()
    date_str = f"{hoy.day} {meses[hoy.month-1]} {hoy.year}"
    return int(count or 0), shot_files, date_str

_db_count, _db_files, _db_date = load_db_stats(engine)
_db_count_fmt = f"{_db_count:,}".replace(",", ".")

# ── Mapa de cancha ────────────────────────────────────────────────────────────
def shot_map(df, title=""):
    fig = go.Figure()

    # Heatmap de densidad — 'line' va al nivel raíz del trace, NO dentro de contours
    fig.add_trace(go.Histogram2dContour(
        x=df["x"], y=df["y"],
        colorscale=[
            [0.00, "rgba(0,0,0,0)"],
            [0.20, "rgba(79,195,247,0.35)"],
            [0.50, "rgba(124,77,255,0.75)"],
            [0.78, "rgba(239,83,80,0.90)"],
            [1.00, "rgba(255,235,59,1.00)"],
        ],
        contours=dict(coloring="heatmap", showlines=False),
        line=dict(width=0),
        nbinsx=40, nbinsy=28,
        showscale=True,
        colorbar=dict(
            title=dict(text="Densidad", font=dict(family=FONT_H, size=9, color=C_CYAN)),
            tickfont=dict(family=FONT_B, size=10, color="#c9d1d9"),
            outlinewidth=0, thickness=12, len=0.75,
        ),
    ))

    shapes = [
        # Borde cancha
        dict(type="rect", x0=-1, x1=100, y0=-42.5, y1=42.5,
             line=dict(color="rgba(220,235,255,0.5)", width=1.5), fillcolor="rgba(0,0,0,0)"),
        # Línea azul (zona ofensiva)
        dict(type="line", x0=25, x1=25, y0=-42.5, y1=42.5,
             line=dict(color="rgba(79,195,247,0.9)", width=2.5)),
        # Línea central
        dict(type="line", x0=0, x1=0, y0=-42.5, y1=42.5,
             line=dict(color="rgba(255,255,255,0.35)", width=1.5)),
        # Línea de gol (roja)
        dict(type="line", x0=89, x1=89, y0=-42.5, y1=42.5,
             line=dict(color="rgba(239,83,80,0.95)", width=2.5)),
        # Red / net
        dict(type="rect", x0=89, x1=93, y0=-3.1, y1=3.1,
             line=dict(color="rgba(239,83,80,1)", width=2),
             fillcolor="rgba(239,83,80,0.15)"),
        # Crease (semicírculo arquero)
        dict(type="circle", x0=83, x1=95, y0=-6, y1=6,
             line=dict(color="rgba(120,170,255,0.8)", width=1.5, dash="dot"),
             fillcolor="rgba(0,0,0,0)"),
        # Círculo cara a cara superior
        dict(type="circle", x0=54, x1=84, y0=7, y1=37,
             line=dict(color="rgba(79,195,247,0.4)", width=1.2), fillcolor="rgba(0,0,0,0)"),
        # Círculo cara a cara inferior
        dict(type="circle", x0=54, x1=84, y0=-37, y1=-7,
             line=dict(color="rgba(79,195,247,0.4)", width=1.2), fillcolor="rgba(0,0,0,0)"),
        # Punto faceoff superior
        dict(type="circle", x0=68.2, x1=69.8, y0=21.2, y1=22.8,
             line=dict(color=C_RED, width=1), fillcolor=C_RED),
        # Punto faceoff inferior
        dict(type="circle", x0=68.2, x1=69.8, y0=-22.8, y1=-21.2,
             line=dict(color=C_RED, width=1), fillcolor=C_RED),
    ]

    annotations = [
        dict(x=12, y=45.5, text="ZONA NEUTRAL", showarrow=False,
             font=dict(family=FONT_H, size=8, color="rgba(79,195,247,0.45)")),
        dict(x=57, y=45.5, text="ZONA OFENSIVA", showarrow=False,
             font=dict(family=FONT_H, size=8, color="rgba(239,83,80,0.55)")),
        dict(x=91, y=5.8, text="NET", showarrow=False,
             font=dict(family=FONT_H, size=7, color="rgba(239,83,80,0.9)")),
    ]

    base_layout(fig, title)
    fig.update_layout(
        plot_bgcolor="rgba(0,10,25,0.95)",
        height=460,
        shapes=shapes,
        annotations=annotations,
        xaxis=dict(range=[-5, 102], title="Coordenada X (pies)"),
        yaxis=dict(range=[-48, 52], title="Coordenada Y (pies)",
                   scaleanchor="x", scaleratio=1),
    )
    return fig

# ── Banner ─────────────────────────────────────────────────────────────────────
_logo_tag = f'<img src="data:image/png;base64,{_LOGO}" style="height:80px;width:auto;filter:drop-shadow(0 0 18px rgba(79,195,247,0.55));flex-shrink:0;">' if _LOGO else ""
st.markdown(f"""
<div class="banner">
  <div style="display:flex;align-items:center;justify-content:center;gap:24px;position:relative;z-index:1;">
    {_logo_tag}
    <div class="banner-title">IceStats</div>
  </div>
</div>
""", unsafe_allow_html=True)

tab_dir, tab_ent, tab_rec = st.tabs(["DIRECTIVOS", "ENTRENADOR", "RECLUTADOR"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DIRECTIVOS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dir:
    sh("Filtros de análisis")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        idx = teams.index("TOR") if "TOR" in teams else 0
        team_d = st.selectbox("Franquicia", teams, index=idx, key="team_d")
    with col2:
        season_range = st.select_slider("Rango de temporadas", options=seasons,
                                        value=(seasons[0], seasons[-1]), key="seasons_d")
    with col3:
        game_type = st.selectbox("Tipo de partido", ["Todos","Regular","Playoffs"], key="gt_d")

    pc = {"Todos":"","Regular":'AND "isPlayoffGame"=0',"Playoffs":'AND "isPlayoffGame"=1'}[game_type]
    s1, s2 = int(season_range[0]), int(season_range[1])

    with st.spinner("Cargando datos históricos..."):
        df_hist = run_query(engine, f"""
            SELECT season,
                   SUM(CASE WHEN "isHomeTeam"=1 AND "homeTeamCode"=:t THEN "xGoal"
                            WHEN "isHomeTeam"=0 AND "awayTeamCode"=:t THEN "xGoal" ELSE 0 END) AS xgf,
                   SUM(CASE WHEN "isHomeTeam"=0 AND "homeTeamCode"=:t THEN "xGoal"
                            WHEN "isHomeTeam"=1 AND "awayTeamCode"=:t THEN "xGoal" ELSE 0 END) AS xga,
                   SUM(CASE WHEN "isHomeTeam"=1 AND "homeTeamCode"=:t THEN "goal"
                            WHEN "isHomeTeam"=0 AND "awayTeamCode"=:t THEN "goal" ELSE 0 END) AS goals,
                   COUNT(CASE WHEN ("isHomeTeam"=1 AND "homeTeamCode"=:t)
                               OR  ("isHomeTeam"=0 AND "awayTeamCode"=:t) THEN 1 END) AS shots
            FROM shots
            WHERE ("homeTeamCode"=:t OR "awayTeamCode"=:t)
              AND season BETWEEN :s1 AND :s2 {pc}
            GROUP BY season ORDER BY season
        """, {"t": team_d, "s1": s1, "s2": s2})

    df_hist["xGF%"] = (df_hist["xgf"] / (df_hist["xgf"] + df_hist["xga"]) * 100).round(1)

    st.divider()
    sh("Resumen del periodo")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("xGoals generados",  f"{df_hist['xgf'].sum():.0f}")
    m2.metric("Goles reales",       f"{df_hist['goals'].sum():.0f}")
    m3.metric("Disparos totales",   f"{df_hist['shots'].sum():,.0f}")
    m4.metric("xGF% promedio",      f"{df_hist['xGF%'].mean():.1f}%")

    st.divider()
    sh("Evolución xGoal% por temporada")
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(
        x=df_hist["season"], y=df_hist["xGF%"], mode="lines+markers", name="xGF%",
        line=dict(color=C_CYAN, width=2.5),
        marker=dict(size=8, color=C_CYAN, line=dict(width=2, color=C_PURP)),
        fill="tozeroy", fillcolor="rgba(79,195,247,0.05)",
        hovertemplate="<b>%{x}</b><br>xGF%%: %{y:.1f}<extra></extra>",
    ))
    fig_hist.add_hline(y=50, line_dash="dash", line_color=C_RED, line_width=1,
                       annotation_text="50% — equilibrio",
                       annotation_font=dict(color=C_RED, family=FONT_H, size=9))
    base_layout(fig_hist)
    fig_hist.update_layout(yaxis=dict(range=[30,70]), xaxis_title="Temporada", yaxis_title="xGoal%")
    st.plotly_chart(fig_hist, use_container_width=True)

    st.divider()
    sh(f"Ranking de franquicias — Temporada {s2}")
    with st.spinner("Comparando equipos..."):
        df_liga = run_query(engine, f"""
            SELECT CASE WHEN "isHomeTeam"=1 THEN "homeTeamCode" ELSE "awayTeamCode" END AS team,
                   SUM("xGoal") AS xgf, SUM("goal") AS goals, COUNT(*) AS shots
            FROM shots WHERE season=:season {pc}
            GROUP BY 1 ORDER BY xgf DESC
        """, {"season": s2})

    colors = [C_RED if t == team_d else "rgba(79,195,247,0.45)" for t in df_liga["team"]]
    fig_liga = go.Figure(go.Bar(
        x=df_liga["team"], y=df_liga["xgf"], marker_color=colors,
        hovertemplate="<b>%{x}</b><br>xGF: %{y:.1f}<extra></extra>",
    ))
    base_layout(fig_liga, "xGoals For por equipo")
    fig_liga.update_layout(xaxis_tickangle=45)
    st.plotly_chart(fig_liga, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ENTRENADOR
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ent:
    sh("Parámetros tácticos")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        idx = teams.index("TOR") if "TOR" in teams else 0
        team_e = st.selectbox("Equipo", teams, index=idx, key="team_e")
    with col2:
        season_e = int(st.selectbox("Temporada", seasons[::-1], key="season_e"))
    with col3:
        sit_e = st.selectbox("Situación", ["Todas","5v5","PP","PK","EN"], key="sit_e")
    with col4:
        home_e = st.selectbox("Condición", ["Local y visitante","Local","Visitante"], key="home_e")

    sit_cond  = "" if sit_e=="Todas" else f'AND "gameSituation"=\'{sit_e}\''
    home_cond = {
        "Local y visitante": '(("homeTeamCode"=:t AND "isHomeTeam"=1) OR ("awayTeamCode"=:t AND "isHomeTeam"=0))',
        "Local":             '("homeTeamCode"=:t AND "isHomeTeam"=1)',
        "Visitante":         '("awayTeamCode"=:t AND "isHomeTeam"=0)',
    }[home_e]

    st.divider()
    sh("Mapa de calor — Zonas de peligro")

    with st.spinner("Procesando coordenadas de tiro..."):
        df_map = run_query(engine, f"""
            SELECT "xCordAdjusted" AS x, "yCordAdjusted" AS y, "dangerZone", "xGoal", "goal"
            FROM shots
            WHERE {home_cond} AND season=:season AND "xCordAdjusted" IS NOT NULL {sit_cond}
            LIMIT 15000
        """, {"t": team_e, "season": season_e})

    fig_map = shot_map(df_map, f"Mapa de tiros — {team_e}  |  Temporada {season_e}")
    st.plotly_chart(fig_map, use_container_width=True)

    st.divider()
    col_e1, col_e2 = st.columns(2)

    with col_e1:
        sh("xGoal por situación de juego")
        df_sit = run_query(engine, f"""
            SELECT "gameSituation" AS s, SUM("xGoal") AS xgoal,
                   SUM("goal") AS goles, COUNT(*) AS disparos
            FROM shots WHERE {home_cond} AND season=:season
            GROUP BY 1 ORDER BY xgoal DESC
        """, {"t": team_e, "season": season_e})

        fig_sit = go.Figure(go.Bar(
            x=df_sit["s"], y=df_sit["xgoal"],
            marker=dict(color=df_sit["xgoal"],
                        colorscale=[[0,C_CYAN],[0.5,C_PURP],[1,C_RED]],
                        line=dict(color="rgba(79,195,247,0.2)", width=0.5)),
            hovertemplate="<b>%{x}</b><br>xGoal: %{y:.2f}<extra></extra>",
        ))
        base_layout(fig_sit, "xGoals por situación")
        st.plotly_chart(fig_sit, use_container_width=True)

    with col_e2:
        sh("Conversión por tipo de disparo")
        df_type = run_query(engine, f"""
            SELECT "shotType" AS tipo, COUNT(*) AS disparos,
                   SUM("goal") AS goles,
                   ROUND(SUM("goal")::numeric/NULLIF(COUNT(*),0)*100,1) AS conv_pct
            FROM shots
            WHERE {home_cond} AND season=:season AND "shotType" IS NOT NULL {sit_cond}
            GROUP BY 1 ORDER BY disparos DESC
        """, {"t": team_e, "season": season_e})

        fig_type = px.bar(df_type, x="tipo", y="conv_pct", color="disparos",
                          color_continuous_scale=[[0,C_CYAN],[0.5,C_PURP],[1,C_RED]],
                          labels={"tipo":"Tipo","conv_pct":"% Conversión","disparos":"N Disparos"})
        base_layout(fig_type, "Conversión % por tipo de disparo")
        st.plotly_chart(fig_type, use_container_width=True)

    st.divider()
    sh("Análisis de transiciones — Rush")
    df_rush = run_query(engine, f"""
        SELECT SUM(CASE WHEN "shotRush"=1 THEN 1       ELSE 0 END) AS rn,
               SUM(CASE WHEN "shotRush"=1 THEN "xGoal" ELSE 0 END) AS rxg,
               SUM(CASE WHEN "shotRush"=1 THEN "goal"  ELSE 0 END) AS rg,
               SUM(CASE WHEN "shotRush"=0 THEN 1       ELSE 0 END) AS nn,
               SUM(CASE WHEN "shotRush"=0 THEN "xGoal" ELSE 0 END) AS nxg,
               SUM(CASE WHEN "shotRush"=0 THEN "goal"  ELSE 0 END) AS ng
        FROM shots WHERE {home_cond} AND season=:season {sit_cond}
    """, {"t": team_e, "season": season_e})
    r = df_rush.iloc[0]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Tiros en rush",  f"{int(r['rn']):,}",  delta=f"{int(r['rg'])} goles")
    c2.metric("xGoal en rush",  f"{r['rxg']:.1f}")
    c3.metric("Tiros normales", f"{int(r['nn']):,}", delta=f"{int(r['ng'])} goles")
    c4.metric("xGoal normales", f"{r['nxg']:.1f}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — RECLUTADOR
# ═══════════════════════════════════════════════════════════════════════════════
with tab_rec:
    sh("Parámetros de búsqueda")
    col1, col2, col3 = st.columns([1,1,2])
    with col1: season_r = int(st.selectbox("Temporada", seasons[::-1], key="season_r"))
    with col2: position_r = st.selectbox("Posición", ["Todas","C","L","R","D"], key="pos_r")
    with col3: min_shots = st.slider("Mínimo de disparos", 10, 300, 50, key="min_shots_r")

    pos_cond = "" if position_r=="Todas" else f'AND "playerPositionThatDidEvent"=\'{position_r}\''

    st.divider()
    sh("Ranking ofensivo — Top jugadores")
    with st.spinner("Calculando métricas avanzadas..."):
        df_rank = run_query(engine, f"""
            SELECT "shooterName" AS jugador, "playerPositionThatDidEvent" AS pos,
                   COUNT(*) AS disparos, SUM("goal") AS goles,
                   ROUND(SUM("xGoal")::numeric,2) AS xgoal,
                   ROUND(SUM("goal")::numeric/NULLIF(COUNT(*),0)*100,1) AS conv_pct,
                   ROUND((SUM("goal")-SUM("xGoal"))::numeric,2) AS goe
            FROM shots
            WHERE season=:season AND "shooterName" IS NOT NULL {pos_cond}
            GROUP BY 1,2 HAVING COUNT(*)>=:ms
            ORDER BY xgoal DESC LIMIT 30
        """, {"season": season_r, "ms": min_shots})

    col_r1, col_r2 = st.columns([1,1])
    with col_r1:
        st.dataframe(df_rank, use_container_width=True, hide_index=True)
    with col_r2:
        fig_rank = go.Figure(go.Bar(
            x=df_rank.head(15)["jugador"], y=df_rank.head(15)["xgoal"],
            marker=dict(color=df_rank.head(15)["goles"],
                        colorscale=[[0,C_CYAN],[0.5,C_PURP],[1,C_RED]],
                        line=dict(color="rgba(79,195,247,0.15)",width=0.5)),
            hovertemplate="<b>%{x}</b><br>xGoal: %{y:.2f}<extra></extra>",
        ))
        base_layout(fig_rank, "Top 15 — xGoal acumulado")
        fig_rank.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_rank, use_container_width=True)

    st.divider()
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        sh("Jugadores Clutch — Alta presión")
        df_clutch = run_query(engine, f"""
            SELECT "shooterName" AS jugador, COUNT(*) AS tiros,
                   SUM("goal") AS goles, ROUND(SUM("xGoal")::numeric,2) AS xgoal,
                   ROUND(SUM("goal")::numeric/NULLIF(COUNT(*),0)*100,1) AS conv
            FROM shots
            WHERE season=:season AND "isClutchSituation"=TRUE
              AND "shooterName" IS NOT NULL {pos_cond}
            GROUP BY 1 HAVING COUNT(*)>=:ms
            ORDER BY goles DESC LIMIT 15
        """, {"season": season_r, "ms": max(min_shots//4,5)})

        fig_clutch = go.Figure(go.Bar(
            x=df_clutch["jugador"], y=df_clutch["goles"],
            marker=dict(color=df_clutch["conv"],
                        colorscale=[[0,C_ORG],[1,C_RED]],
                        line=dict(color="rgba(239,83,80,0.2)",width=0.5)),
            hovertemplate="<b>%{x}</b><br>Goles clutch: %{y}<extra></extra>",
        ))
        base_layout(fig_clutch, "Goles en situaciones de alta presión")
        fig_clutch.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_clutch, use_container_width=True)

    with col_c2:
        sh("Porteros — Goals Saved Above Expected")
        df_goalies = run_query(engine, f"""
            SELECT "goalieNameForShot" AS portero, COUNT(*) AS disparos,
                   SUM("goal") AS concedidos,
                   ROUND(SUM("xGoal")::numeric,2) AS xgoal_esp,
                   ROUND((SUM("xGoal")-SUM("goal"))::numeric,2) AS gsae,
                   ROUND((1-SUM("goal")::numeric/NULLIF(COUNT(*),0))*100,1) AS sv_pct
            FROM shots
            WHERE season=:season AND "goalieNameForShot" IS NOT NULL
            GROUP BY 1 HAVING COUNT(*)>=100
            ORDER BY gsae DESC LIMIT 15
        """, {"season": season_r})

        fig_goalie = go.Figure(go.Bar(
            x=df_goalies["portero"], y=df_goalies["gsae"],
            marker=dict(color=df_goalies["sv_pct"],
                        colorscale=[[0,C_CYAN],[1,C_GRN]],
                        line=dict(color="rgba(102,187,106,0.2)",width=0.5)),
            hovertemplate="<b>%{x}</b><br>GSAE: %{y:.2f}<extra></extra>",
        ))
        base_layout(fig_goalie, "Goals Saved Above Expected")
        fig_goalie.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_goalie, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="db-footer">
  <div class="db-sync-status"><span class="db-dot"></span>Base sincronizada</div>
  <div class="db-sync-file">{_db_files}</div>
  <div class="db-sync-meta">{_db_count_fmt} registros &nbsp;&middot;&nbsp; {_db_date}</div>
</div>
""", unsafe_allow_html=True)
