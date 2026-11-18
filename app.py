import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Exportaciones Pelo Fino de Alpaca", layout="wide")

BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE, ".env"))


@st.cache_resource
def get_engine():
    return create_engine(
        os.environ["DATABASE_URL"],
        pool_pre_ping=True,
        pool_recycle=300,
    )


@st.cache_data
def cargar_anual():
    q = text("""
        SELECT anio, fob_usd, peso_neto_kg, peso_bruto_kg
        FROM exportaciones_sector
        WHERE partida_arancelaria = '5105391000'
          AND anio BETWEEN 2016 AND 2025
        ORDER BY anio
    """)
    with get_engine().connect() as conn:
        df = pd.read_sql(q, conn)
    return df.astype(float).assign(anio=lambda d: d["anio"].astype(int))


# ---------- Secciones ----------
def seccion_evolucion(df):
    st.header("3.2. Evolución anual")
    fig = px.bar(df, x="anio", y="fob_usd", text_auto=".3s",
                 labels={"anio": "Año", "fob_usd": "Valor FOB (US$)"})
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis=dict(type="category"), yaxis_tickformat=",")
    st.plotly_chart(fig, use_container_width=True)


def seccion_fob(df):
    st.header("3.3. Valor FOB")
    total = df["fob_usd"].sum()
    mx = df.loc[df["fob_usd"].idxmax()]
    mn = df.loc[df["fob_usd"].idxmin()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("FOB acumulado", f"US$ {total/1e6:,.1f} M")
    c2.metric("FOB promedio anual", f"US$ {df['fob_usd'].mean()/1e6:,.1f} M")
    c3.metric(f"Máximo ({int(mx['anio'])})", f"US$ {mx['fob_usd']/1e6:,.1f} M")
    c4.metric(f"Mínimo ({int(mn['anio'])})", f"US$ {mn['fob_usd']/1e6:,.1f} M")

    rank = df[["anio", "fob_usd"]].copy()
    rank["participacion_pct"] = (rank["fob_usd"] / total * 100).round(2)
    rank["posicion"] = rank["fob_usd"].rank(ascending=False).astype(int)
    rank["anio"] = rank["anio"].astype(str)
    rank = rank.sort_values("posicion")

    fig = px.bar(rank, x="fob_usd", y="anio", orientation="h", text_auto=".3s",
                 labels={"anio": "Año", "fob_usd": "Valor FOB (US$)"})
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_tickformat=",")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(rank, use_container_width=True, hide_index=True)


def seccion_volumen(df):
    st.header("3.4. Volumen físico")
    v = df.copy()
    v["peso_neto_t"] = v["peso_neto_kg"] / 1000
    v["peso_bruto_t"] = v["peso_bruto_kg"] / 1000
    v["embalaje_t"] = v["peso_bruto_t"] - v["peso_neto_t"]
    v["embalaje_pct_pb"] = (v["embalaje_t"] / v["peso_bruto_t"] * 100).round(2)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Peso neto acumulado", f"{v['peso_neto_t'].sum():,.0f} t")
    c2.metric("Peso bruto acumulado", f"{v['peso_bruto_t'].sum():,.0f} t")
    c3.metric("Peso neto promedio anual", f"{v['peso_neto_t'].mean():,.0f} t")
    c4.metric("Embalaje (PB − PN)", f"{v['embalaje_t'].sum():,.0f} t")

    larga = v.melt(id_vars="anio", value_vars=["peso_neto_t", "peso_bruto_t"],
                   var_name="tipo", value_name="toneladas")
    larga["tipo"] = larga["tipo"].map({"peso_neto_t": "Peso neto",
                                       "peso_bruto_t": "Peso bruto"})
    fig = px.bar(larga, x="anio", y="toneladas", color="tipo", barmode="group",
                 labels={"anio": "Año", "toneladas": "Toneladas", "tipo": ""})
    fig.update_layout(xaxis=dict(type="category"), yaxis_tickformat=",")
    st.plotly_chart(fig, use_container_width=True)

    tabla = v[["anio", "peso_neto_t", "peso_bruto_t", "embalaje_t",
               "embalaje_pct_pb"]].round(2)
    tabla["anio"] = tabla["anio"].astype(int)
    st.dataframe(tabla, use_container_width=True, hide_index=True)


def preparar_derivados(df):
    d = df.copy()
    d["peso_neto_t"] = d["peso_neto_kg"] / 1000
    d["fob_por_t"] = d["fob_usd"] / d["peso_neto_t"]
    d["var_fob_pct"] = d["fob_usd"].pct_change() * 100
    d["var_pn_pct"] = d["peso_neto_t"].pct_change() * 100
    d["var_fob_t_pct"] = d["fob_por_t"].pct_change() * 100
    return d


def seccion_derivados(df):
    st.header("3.5. Indicadores derivados")
    if len(df) < 2:
        st.info("Selecciona al menos 2 años en el filtro para calcular variaciones.")
        return

    d = preparar_derivados(df)
    n = d["anio"].iloc[-1] - d["anio"].iloc[0]
    cagr_fob = ((d["fob_usd"].iloc[-1] / d["fob_usd"].iloc[0]) ** (1 / n) - 1) * 100
    cagr_pn = ((d["peso_neto_t"].iloc[-1] / d["peso_neto_t"].iloc[0]) ** (1 / n) - 1) * 100
    corr = d["fob_usd"].corr(d["peso_neto_t"])
    fob_t_global = d["fob_usd"].sum() / d["peso_neto_t"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Crecimiento anual compuesto FOB", f"{cagr_fob:.1f} %")
    c2.metric("Crecimiento anual compuesto peso neto", f"{cagr_pn:.1f} %")
    c3.metric("FOB por tonelada (periodo)", f"US$ {fob_t_global:,.0f}/t")
    c4.metric("Correlación FOB vs peso neto", f"{corr:.2f}")

    st.subheader("Variación porcentual anual")
    var = d.dropna(subset=["var_fob_pct"]).melt(
        id_vars="anio", value_vars=["var_fob_pct", "var_pn_pct"],
        var_name="indicador", value_name="variacion")
    var["indicador"] = var["indicador"].map({"var_fob_pct": "Var. % FOB",
                                             "var_pn_pct": "Var. % peso neto"})
    fig1 = px.bar(var, x="anio", y="variacion", color="indicador", barmode="group",
                  labels={"anio": "Año", "variacion": "Variación (%)", "indicador": ""})
    fig1.update_layout(xaxis=dict(type="category"))
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("Valor FOB por tonelada")
    fig2 = px.line(d, x="anio", y="fob_por_t", markers=True,
                   labels={"anio": "Año", "fob_por_t": "US$ por tonelada"})
    fig2.update_layout(xaxis=dict(type="category"), yaxis_tickformat=",")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Relación entre valor FOB y peso neto")
    fig3 = px.scatter(d, x="peso_neto_t", y="fob_usd", text="anio",
                      labels={"peso_neto_t": "Peso neto (t)", "fob_usd": "Valor FOB (US$)"})
    fig3.update_traces(textposition="top center", marker=dict(size=10))
    fig3.update_layout(xaxis_tickformat=",", yaxis_tickformat=",")
    st.plotly_chart(fig3, use_container_width=True)

    tabla = d[["anio", "var_fob_pct", "var_pn_pct", "fob_por_t", "var_fob_t_pct"]].round(1)
    tabla["anio"] = tabla["anio"].astype(int)
    st.dataframe(tabla, use_container_width=True, hide_index=True)


def seccion_tablero(df):
    st.header("3.6. Tablero de inteligencia de negocios")
    if len(df) < 2:
        st.info("Selecciona al menos 2 años en el filtro.")
        return

    d = preparar_derivados(df)
    n = d["anio"].iloc[-1] - d["anio"].iloc[0]
    cagr_fob = ((d["fob_usd"].iloc[-1] / d["fob_usd"].iloc[0]) ** (1 / n) - 1) * 100
    fob_t_global = d["fob_usd"].sum() / d["peso_neto_t"].sum()
    ult = d.iloc[-1]

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("FOB acumulado", f"US$ {d['fob_usd'].sum()/1e6:,.1f} M")
    k2.metric("Peso neto acumulado", f"{d['peso_neto_t'].sum():,.0f} t")
    k3.metric("FOB por tonelada", f"US$ {fob_t_global:,.0f}/t")
    k4.metric("Crecimiento anual compuesto FOB", f"{cagr_fob:.1f} %")
    k5.metric(f"FOB {int(ult['anio'])}", f"US$ {ult['fob_usd']/1e6:,.1f} M",
              delta=f"{ult['var_fob_pct']:.1f} % vs año anterior")

    opciones = {
        "Valor FOB (US$)": ("fob_usd", "var_fob_pct"),
        "Peso neto (t)": ("peso_neto_t", "var_pn_pct"),
        "FOB por tonelada (US$/t)": ("fob_por_t", "var_fob_t_pct"),
    }
    elegido = st.radio("Indicador a visualizar", list(opciones), horizontal=True)
    col, var_col = opciones[elegido]

    a, b = st.columns(2)
    with a:
        st.subheader(f"Evolución anual: {elegido}")
        f1 = px.bar(d, x="anio", y=col, text_auto=".3s",
                    labels={"anio": "Año", col: elegido})
        f1.update_layout(xaxis=dict(type="category"), yaxis_tickformat=",")
        st.plotly_chart(f1, use_container_width=True)
    with b:
        st.subheader("Variación porcentual anual")
        f2 = px.bar(d.dropna(subset=[var_col]), x="anio", y=var_col,
                    text_auto=".1f",
                    labels={"anio": "Año", var_col: "Variación (%)"})
        f2.update_layout(xaxis=dict(type="category"))
        st.plotly_chart(f2, use_container_width=True)

    c, e = st.columns(2)
    with c:
        st.subheader("Relación FOB vs peso neto")
        f3 = px.scatter(d, x="peso_neto_t", y="fob_usd", text="anio",
                        labels={"peso_neto_t": "Peso neto (t)", "fob_usd": "Valor FOB (US$)"})
        f3.update_traces(textposition="top center", marker=dict(size=10))
        f3.update_layout(xaxis_tickformat=",", yaxis_tickformat=",")
        st.plotly_chart(f3, use_container_width=True)
    with e:
        st.subheader(f"Ranking de años: {elegido}")
        rank = d[["anio", col]].sort_values(col, ascending=False).copy()
        rank["anio"] = rank["anio"].astype(int).astype(str)
        rank[col] = rank[col].round(1)
        st.dataframe(rank, use_container_width=True, hide_index=True)

    if st.checkbox("Mostrar tabla completa de datos"):
        completa = d[["anio", "fob_usd", "peso_neto_t", "fob_por_t",
                      "var_fob_pct", "var_pn_pct", "var_fob_t_pct"]].round(2)
        completa["anio"] = completa["anio"].astype(int)
        st.dataframe(completa, use_container_width=True, hide_index=True)


# ---------- Página ----------
st.title("Exportaciones peruanas de pelo fino de alpaca o llama")
st.caption("Subpartida 5105391000 · Fuente: SUNAT")

datos = cargar_anual()

st.sidebar.title("Menú")
seccion = st.sidebar.radio(
    "Sección",
    ["Evolución anual", "Valor FOB", "Volumen físico",
     "Indicadores derivados", "Tablero BI"],
)
anio_min, anio_max = st.sidebar.slider(
    "Rango de años", 2016, 2025, (2016, 2025)
)
df = datos[datos["anio"].between(anio_min, anio_max)]

if seccion == "Evolución anual":
    seccion_evolucion(df)
elif seccion == "Valor FOB":
    seccion_fob(df)
elif seccion == "Volumen físico":
    seccion_volumen(df)
elif seccion == "Indicadores derivados":
    seccion_derivados(df)
else:
    seccion_tablero(df)