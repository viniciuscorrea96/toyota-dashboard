import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Toyota | Vendas", layout="wide")

# =========================
# Helpers
# =========================
def brl(x):
    try:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

def parse_date_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df

@st.cache_data
def load_excel(path: str, sheet: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet)

# =========================
# Sidebar: arquivos
# =========================
st.sidebar.title("📂 Fonte de Dados")
painel_path = st.sidebar.text_input("Arquivo", "dados painel.xlsx")

if not os.path.exists(painel_path):
    st.error(f"Não achei o arquivo: {painel_path}. Confirme se ele está no repositório com esse nome.")
    st.stop()

# Carrega abas
vendas = load_excel(painel_path, "painel toyota")
metas = load_excel(painel_path, "metas")

# Tipos
vendas = parse_date_col(vendas, "Data")
vendas["Total Nota"] = pd.to_numeric(vendas.get("Total Nota"), errors="coerce").fillna(0)
vendas["Descontos por item"] = pd.to_numeric(vendas.get("Descontos por item"), errors="coerce").fillna(0)

metas["Objetivo"] = pd.to_numeric(metas.get("Objetivo"), errors="coerce").fillna(0)

# =========================
# Default mês/ano: último mês com dado
# =========================
if vendas["Data"].notna().any():
    last_date = vendas["Data"].max()
    default_year = int(last_date.year)
    default_month = int(last_date.month)
else:
    st.error("A coluna 'Data' não está sendo reconhecida como data. Verifique o formato.")
    st.stop()

# =========================
# Sidebar: referência e filtros
# =========================
st.sidebar.markdown("---")
st.sidebar.title("📅 Referência")

years = sorted(vendas["Data"].dropna().dt.year.unique().tolist())
year = st.sidebar.selectbox("Ano", years, index=years.index(default_year) if default_year in years else len(years)-1)

months_avail = sorted(vendas[vendas["Data"].dt.year == year]["Data"].dt.month.unique().tolist())
month = st.sidebar.selectbox("Mês", months_avail, index=months_avail.index(default_month) if default_month in months_avail else len(months_avail)-1)

dfm = vendas[(vendas["Data"].dt.year == year) & (vendas["Data"].dt.month == month)].copy()

st.sidebar.markdown("---")
st.sidebar.title("🎛️ Filtros")

def filter_select(df, col, label):
    if col not in df.columns:
        return df, None
    opts = ["Todos"] + sorted(df[col].dropna().unique().tolist())
    sel = st.sidebar.selectbox(label, opts, index=0)
    if sel != "Todos":
        df = df[df[col] == sel]
    return df, sel

dfm, regional_sel = filter_select(dfm, "Regional", "Regional")
dfm, unidade_sel  = filter_select(dfm, "Unidade", "Unidade")
dfm, vendedor_sel = filter_select(dfm, "Nome_vendedor", "Vendedor")

# =========================
# Header + sanity check
# =========================
st.title("🚗 Toyota | Vendas (Python)")
st.caption(f"Referência: {month:02d}/{year} • Linhas após filtros: {len(dfm):,}".replace(",", "."))

with st.expander("🔎 Diagnóstico rápido (pra não ficar 'site estéril')", expanded=False):
    st.write("Período total da base:", str(vendas["Data"].min().date()), "→", str(vendas["Data"].max().date()))
    st.write("Abas carregadas: painel toyota + metas")
    st.write("Colunas disponíveis (painel toyota):", list(vendas.columns))

if dfm.empty:
    st.warning("Sem dados para esse mês/filtros. Troque o mês/ano na lateral (o default já é o último mês com dado).")
    st.stop()

# =========================
# KPIs
# =========================
fat = dfm["Total Nota"].sum()
notas = len(dfm)
ticket = fat / notas if notas else 0
desc_val = dfm["Descontos por item"].sum()
desc_pct = (desc_val / fat) if fat else 0

# Meta: usar SOMENTE se for fevereiro (sua meta atual é apenas fevereiro)
meta_total = metas["Objetivo"].sum() if month == 2 else np.nan
ating = (fat / meta_total) if (month == 2 and meta_total) else np.nan
gap = (meta_total - fat) if month == 2 else np.nan

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Faturamento (mês)", brl(fat))
c2.metric("Notas", f"{notas:,}".replace(",", "."))
c3.metric("Ticket Médio", brl(ticket))
c4.metric("Desconto (R$)", brl(desc_val))
c5.metric("Desconto (%)", f"{desc_pct*100:.2f}%".replace(".", ","))

if month == 2:
    c6.metric("Meta (Fev)", brl(meta_total))
    c7, c8 = st.columns(2)
    c7.metric("Atingimento", f"{ating*100:.1f}%".replace(".", ",") if not np.isnan(ating) else "—")
    c8.metric("Gap (Meta - Fat)", brl(gap) if not np.isnan(gap) else "—")
else:
    c6.metric("Meta (Fev)", "—")
    st.info("Meta no arquivo está apenas para Fevereiro. Selecione mês 2 para ver atingimento.")

# =========================
# Tabs
# =========================
tab_exec, tab_reg, tab_uni, tab_vend = st.tabs(["Executivo", "Regional", "Unidade", "Vendedor (MTD)"])

with tab_exec:
    st.subheader("Faturamento diário")
    daily = dfm.groupby(dfm["Data"].dt.date, as_index=False)["Total Nota"].sum()
    fig = px.area(daily, x="Data", y="Total Nota")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 20 vendedores (mês)")
    topv = dfm.groupby("Nome_vendedor", as_index=False)["Total Nota"].sum().sort_values("Total Nota", ascending=False).head(20)
    fig2 = px.bar(topv, x="Total Nota", y="Nome_vendedor", orientation="h")
    st.plotly_chart(fig2, use_container_width=True)

with tab_reg:
    st.subheader("Ranking por Regional")
    reg = dfm.groupby("Regional", as_index=False).agg(
        Faturamento=("Total Nota", "sum"),
        Notas=("Total Nota", "size"),
        Desconto=("Descontos por item", "sum"),
    )
    reg["Ticket"] = reg["Faturamento"] / reg["Notas"].replace(0, np.nan)
    reg = reg.sort_values("Faturamento", ascending=False)
    st.dataframe(reg, use_container_width=True)
    st.plotly_chart(px.bar(reg, x="Faturamento", y="Regional", orientation="h"), use_container_width=True)

with tab_uni:
    st.subheader("Ranking por Unidade")
    uni = dfm.groupby(["Unidade", "Regional"], as_index=False).agg(
        Faturamento=("Total Nota", "sum"),
        Notas=("Total Nota", "size"),
        Desconto=("Descontos por item", "sum"),
    )
    uni["Ticket"] = uni["Faturamento"] / uni["Notas"].replace(0, np.nan)
    uni = uni.sort_values("Faturamento", ascending=False)
    st.dataframe(uni, use_container_width=True)
    st.plotly_chart(px.bar(uni.head(25), x="Faturamento", y="Unidade", orientation="h", color="Regional"), use_container_width=True)

with tab_vend:
    st.subheader("Comparativo MTD (mês atual vs mesmo período mês anterior)")

    # Se o filtro do sidebar não escolheu um vendedor, deixa escolher aqui
    vendedores = sorted(vendas["Nome_vendedor"].dropna().unique().tolist())
    vend = vendedor_sel if (vendedor_sel and vendedor_sel != "Todos") else st.selectbox("Escolha o vendedor", vendedores)

    base = vendas[vendas["Nome_vendedor"] == vend].copy()

    # mês atual
    cur = base[(base["Data"].dt.year == year) & (base["Data"].dt.month == month)].copy()
    if cur.empty:
        st.warning("Esse vendedor não tem vendas no mês selecionado.")
        st.stop()

    corte = int(cur["dia_mes"].max())  # mesmo comportamento do BI: até o dia com dado
    fat_atual = cur[cur["dia_mes"] <= corte]["Total Nota"].sum()

    # mês anterior
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    prev = base[(base["Data"].dt.year == prev_year) & (base["Data"].dt.month == prev_month) & (base["dia_mes"] <= corte)].copy()
    fat_prev = prev["Total Nota"].sum()

    desvio_rs = fat_atual - fat_prev
    desvio_pct = (fat_atual / fat_prev - 1) if fat_prev else np.nan

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faturamento Atual", brl(fat_atual))
    c2.metric("Mesmo período mês anterior", brl(fat_prev))
    c3.metric("(R$) Desvio", brl(desvio_rs))
    c4.metric("% Desvio", "—" if np.isnan(desvio_pct) else f"{desvio_pct*100:.2f}%".replace(".", ","))

    st.markdown("#### MTD acumulado por dia_mes")
    cur_d = cur.groupby("dia_mes", as_index=False)["Total Nota"].sum().sort_values("dia_mes")
    cur_d["MTD"] = cur_d["Total Nota"].cumsum()
    cur_d["Mês"] = f"{month:02d}/{year}"

    prev_full = base[(base["Data"].dt.year == prev_year) & (base["Data"].dt.month == prev_month)].copy()
    prev_d = prev_full.groupby("dia_mes", as_index=False)["Total Nota"].sum().sort_values("dia_mes")
    prev_d = prev_d[prev_d["dia_mes"] <= corte]
    prev_d["MTD"] = prev_d["Total Nota"].cumsum()
    prev_d["Mês"] = f"{prev_month:02d}/{prev_year}"

    mtd_plot = pd.concat([cur_d[["dia_mes","MTD","Mês"]], prev_d[["dia_mes","MTD","Mês"]]], ignore_index=True)
    st.plotly_chart(px.area(mtd_plot, x="dia_mes", y="MTD", color="Mês"), use_container_width=True)

    st.markdown("#### Diário por dia_mes")
    cur_day = cur.groupby("dia_mes", as_index=False)["Total Nota"].sum()
    cur_day["Mês"] = f"{month:02d}/{year}"

    prev_day = prev_full.groupby("dia_mes", as_index=False)["Total Nota"].sum()
    prev_day = prev_day[prev_day["dia_mes"] <= corte]
    prev_day["Mês"] = f"{prev_month:02d}/{prev_year}"

    day_plot = pd.concat([cur_day, prev_day], ignore_index=True)
    st.plotly_chart(px.area(day_plot, x="dia_mes", y="Total Nota", color="Mês"), use_container_width=True)

