import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Toyota | Dashboard", layout="wide")

# =========================
# Helpers
# =========================
def brl(x):
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_date(df, col):
    df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df

@st.cache_data
def load_data():
    df = pd.read_excel("dados painel.xlsx", sheet_name="dezembro")
    return df

# =========================
# LOAD
# =========================
df = load_data()

df = parse_date(df, "Data")
df["Total Nota"] = pd.to_numeric(df["Total Nota"], errors="coerce").fillna(0)
df["Descontos por item"] = pd.to_numeric(df["Descontos por item"], errors="coerce").fillna(0)


# =========================
# SIDEBAR FILTROS
# =========================
st.sidebar.title("Referência")

# Base completa (não filtrada)
df_all = load_data()
df_all = parse_date(df_all, "Data")
df_all["Total Nota"] = pd.to_numeric(df_all["Total Nota"], errors="coerce").fillna(0)
df_all["Descontos por item"] = pd.to_numeric(df_all["Descontos por item"], errors="coerce").fillna(0)

# Ano/Mês disponíveis na base
anos = sorted(df_all["Data"].dropna().dt.year.unique().tolist())
ano = st.sidebar.selectbox("Ano", anos, index=len(anos)-1)

meses = sorted(df_all[df_all["Data"].dt.year == ano]["Data"].dt.month.unique().tolist())
mes = st.sidebar.selectbox("Mês", meses, index=len(meses)-1)

# Filtra por Ano/Mês primeiro
df = df_all[(df_all["Data"].dt.year == ano) & (df_all["Data"].dt.month == mes)].copy()

st.sidebar.markdown("---")
st.sidebar.title("Filtros")

regional = st.sidebar.selectbox("Regional", ["Todos"] + sorted(df["Regional"].dropna().unique().tolist()))
if regional != "Todos":
    df = df[df["Regional"] == regional]

unidade = st.sidebar.selectbox("Unidade", ["Todos"] + sorted(df["Unidade"].dropna().unique().tolist()))
if unidade != "Todos":
    df = df[df["Unidade"] == unidade]

vendedor = st.sidebar.selectbox("Vendedor", ["Todos"] + sorted(df["Nome_vendedor"].dropna().unique().tolist()))
if vendedor != "Todos":
    df = df[df["Nome_vendedor"] == vendedor]

# =========================
# KPIs SUPERIORES (IGUAL BI)
# =========================
fat = df["Total Nota"].sum()
notas = len(df)
ticket = fat / notas if notas else 0
desc_val = df["Descontos por item"].sum()
desc_pct = (desc_val / fat) if fat else 0

# Meta (no seu arquivo está na aba "metas" e pelo que você disse é só Fevereiro)
metas = pd.read_excel("dados painel.xlsx", sheet_name="metas")

def parse_brl(x):
    if pd.isna(x): 
        return 0.0
    s = str(x).replace("R$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    return pd.to_numeric(s, errors="coerce") or 0.0

if "Objetivo" in metas.columns:
    metas["Objetivo_num"] = metas["Objetivo"].apply(parse_brl)
else:
    metas["Objetivo_num"] = 0.0

# meta total só aparece no mês 2 (fev). Nos outros meses, deixa em branco (igual você comentou)
meta_total = metas["Objetivo_num"].sum() if mes == 2 else np.nan
ating = (fat / meta_total) if (mes == 2 and meta_total and meta_total > 0) else np.nan

st.title("Toyota | Relatório CPV")

c1, c2, c3 = st.columns(3, gap="large")
c4, c5, c6, c7, c8 = st.columns(5, gap="large")
c1.metric("Faturamento Total", brl(fat))
c2.metric("NFs Emitidas", f"{notas:,}".replace(",", "."))
c3.metric("Ticket Médio", brl(ticket))

c4.metric("Desconto Total (R$)", brl(desc_val))
c5.metric("Desconto (%)", f"{desc_pct*100:.2f}%".replace(".", ","))
c6.metric("Meta", "—" if np.isnan(meta_total) else brl(meta_total))
c7.metric("Atingimento", "—" if np.isnan(ating) else f"{ating*100:.1f}%".replace(".", ","))

# =========================
# ABAS BASEADAS NOS GRÁFICOS
# =========================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Faturamento por Unidade",
    "📈 Evolução por Dia do Mês",
    "🏢 Faturamento por Regional",
    "👤 Performance do Vendedor (MTD)",
    "📋 Detalhes por Nota"
])

# =========================
# 1 - FATURAMENTO POR UNIDADE
# =========================
with tab1:
    st.subheader("Faturamento por Unidade")

    uni = df.groupby("Unidade", as_index=False)["Total Nota"].sum().sort_values("Total Nota", ascending=False)

    fig = px.bar(
        uni,
        x="Total Nota",
        y="Unidade",
        orientation="h"
    )
    st.plotly_chart(fig, use_container_width=True)

# =========================
# 2 - EVOLUÇÃO POR DIA
# =========================
with tab2:
    st.subheader("Evolução do Faturamento por Dias do Mês")

    daily = df.groupby("dia_mes", as_index=False)["Total Nota"].sum().sort_values("dia_mes")

    fig = px.area(daily, x="dia_mes", y="Total Nota")
    st.plotly_chart(fig, use_container_width=True)

# =========================
# 3 - REGIONAL
# =========================
with tab3:
    st.subheader("Faturamento por Regional")

    reg = df.groupby("Regional", as_index=False)["Total Nota"].sum().sort_values("Total Nota", ascending=False)

    fig = px.bar(
        reg,
        x="Total Nota",
        y="Regional",
        orientation="h"
    )
    st.plotly_chart(fig, use_container_width=True)

# =========================
# 4 - MTD VENDEDOR
# =========================
with tab4:
    st.subheader("Comparativo MTD do Vendedor")

    if vendedor == "Todos":
        st.info("Selecione um vendedor no filtro lateral.")
    else:
        base = load_data()
        base = parse_date(base, "Data")
        base["Total Nota"] = pd.to_numeric(base["Total Nota"], errors="coerce").fillna(0)

        cur = base[base["Nome_vendedor"] == vendedor].copy()
        cur = cur.sort_values("dia_mes")

        cur["MTD"] = cur["Total Nota"].cumsum()

        fig = px.area(cur, x="dia_mes", y="MTD")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# 5 - DETALHES POR NOTA (TABELA)
# =========================
with tab5:
    st.subheader("Detalhamento das Notas")

    cols_show = [
        "Número",
        "Nome_vendedor",
        "Unidade",
        "Cliente",
        "Total Nota",
        "Descontos por item",
        "Data"
    ]

    available_cols = [c for c in cols_show if c in df.columns]

    st.dataframe(df[available_cols].sort_values("Data"), use_container_width=True)
