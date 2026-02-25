
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from datetime import date

st.set_page_config(page_title="Toyota | Dashboard (Python)", layout="wide")

PAINEL_FILE_DEFAULT = "dados painel.xlsx"
ESTOQUE_FILE_DEFAULT = "Estoque ABC - BI.xlsx"

FATOR_COMPORTAMENTO = 0.20  # igual ao DAX

@st.cache_data
def load_painel(path: str):
    xl = pd.read_excel(path, sheet_name=None)
    sales = xl["painel toyota"].copy()
    metas = xl["metas"].copy()
    return sales, metas

@st.cache_data
def load_estoque(path: str):
    xl = pd.read_excel(path, sheet_name=None)
    est_atual = xl["Sheet1"].copy()
    est_media = xl["estoque_media"].copy()
    return est_atual, est_media

def brl(x):
    try:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

def to_date(df, col):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("⚙️ Fonte de Dados")

painel_file = st.sidebar.text_input("Arquivo de Vendas (dados painel.xlsx)", PAINEL_FILE_DEFAULT)
estoque_file = st.sidebar.text_input("Arquivo de Estoque (Estoque ABC - BI.xlsx)", ESTOQUE_FILE_DEFAULT)

try:
    vendas, metas = load_painel(painel_file)
    est_atual, est_media = load_estoque(estoque_file)
except Exception as e:
    st.error("Não consegui carregar os arquivos. Verifique se os nomes estão corretos e se estão na mesma pasta do app.")
    st.exception(e)
    st.stop()

# ----------------------------
# Preparação Vendas
# ----------------------------
# Coluna de data escolhida: "Data"
vendas = to_date(vendas, "Data")

# Conversões numéricas (ajuste se seus nomes forem diferentes)
for col in ["Total Nota", "Descontos por item"]:
    if col in vendas.columns:
        vendas[col] = pd.to_numeric(vendas[col], errors="coerce").fillna(0)

# Metas (fevereiro)
if "Objetivo" in metas.columns:
    metas["Objetivo"] = pd.to_numeric(metas["Objetivo"], errors="coerce").fillna(0)

# ----------------------------
# Mês de referência (automático) + opção de forçar fevereiro
# ----------------------------
st.sidebar.markdown("---")
st.sidebar.title("📅 Mês de Referência")

hoje = date.today()
mes_auto = hoje.month
ano_auto = hoje.year

forcar_fevereiro = st.sidebar.checkbox("Forçar Fevereiro (meta do mês)", value=(mes_auto != 2))

anos_disponiveis = sorted(vendas["Data"].dropna().dt.year.unique().tolist()) if "Data" in vendas.columns else [ano_auto]
ano_ref = st.sidebar.selectbox("Ano", anos_disponiveis, index=len(anos_disponiveis)-1 if anos_disponiveis else 0)

mes_ref = 2 if forcar_fevereiro else st.sidebar.selectbox("Mês", list(range(1, 13)), index=max(0, min(11, mes_auto-1)))

df = vendas.copy()
if "Data" in df.columns:
    df = df[(df["Data"].dt.year == ano_ref) & (df["Data"].dt.month == mes_ref)]

# ----------------------------
# Filtros (Regional / Unidade / Vendedor)
# ----------------------------
st.sidebar.markdown("---")
st.sidebar.title("🎛️ Filtros")

def add_filter(df, col, label):
    if col not in df.columns:
        return df
    opts = ["Todos"] + sorted(df[col].dropna().unique().tolist())
    sel = st.sidebar.selectbox(label, opts, index=0)
    if sel != "Todos":
        df = df[df[col] == sel]
    return df

df = add_filter(df, "Regional", "Regional")
df = add_filter(df, "Unidade", "Unidade")
df = add_filter(df, "Nome_vendedor", "Vendedor")

# ----------------------------
# KPIs Vendas
# ----------------------------
fat = df["Total Nota"].sum() if "Total Nota" in df.columns else 0
notas = len(df)
ticket = fat / notas if notas else 0
desc_val = df["Descontos por item"].sum() if "Descontos por item" in df.columns else 0
desc_pct = (desc_val / fat) if fat else 0

# Projeção por dias úteis (Seg-Sex). Se quiser feriados BR, a gente adiciona depois.
proj = 0
if "Data" in df.columns and df["Data"].notna().any():
    first_day = pd.Timestamp(ano_ref, mes_ref, 1)
    last_day = (first_day + pd.offsets.MonthEnd(0))
    dias_uteis_total = len(pd.bdate_range(first_day, last_day))
    data_corte = df["Data"].max().normalize()
    dias_uteis_decorridos = len(pd.bdate_range(first_day, min(data_corte, last_day)))
    proj = (fat / dias_uteis_decorridos) * dias_uteis_total if dias_uteis_decorridos else 0

meta_total = metas["Objetivo"].sum() if "Objetivo" in metas.columns else 0
ating = (fat / meta_total) if meta_total else 0
gap_meta = meta_total - fat

# ----------------------------
# Header
# ----------------------------
st.title("🚗 Toyota | Dashboard (Python)")
st.caption(f"Referência: {mes_ref:02d}/{ano_ref}  •  (Forçar Fevereiro = {'Sim' if forcar_fevereiro else 'Não'})")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Faturamento (mês)", brl(fat))
c2.metric("🧾 Notas", f"{notas:,}".replace(",", "."))
c3.metric("🎟️ Ticket Médio", brl(ticket))
c4.metric("🏷️ Desconto (R$)", brl(desc_val))
c5.metric("🏷️ Desconto (%)", f"{desc_pct*100:.2f}%".replace(".", ","))

c6, c7, c8 = st.columns(3)
c6.metric("📈 Projetado (Seg-Sex)", brl(proj))
c7.metric("🎯 Meta (Fev)", brl(meta_total))
c8.metric("✅ Atingimento", f"{ating*100:.1f}%".replace(".", ","))

tabs = st.tabs(["Executivo", "Unidades", "Regionais", "Vendedores", "Estoque ABC"])

# ----------------------------
# Aba Executivo
# ----------------------------
with tabs[0]:
    st.subheader("Evolução diária do faturamento")
    if "Data" in df.columns and df["Data"].notna().any():
        by_day = df.groupby(df["Data"].dt.date, as_index=False)["Total Nota"].sum()
        fig = px.line(by_day, x="Data", y="Total Nota")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para o mês/filtros selecionados.")

# ----------------------------
# Aba Unidades (com meta)
# ----------------------------
with tabs[1]:
    st.subheader("Ranking por Unidade + Meta (Fev)")
    if "Unidade" in df.columns:
        by_unit = df.groupby(["Unidade", "Regional"], as_index=False).agg(
            Faturamento=("Total Nota", "sum"),
            Notas=("Total Nota", "size"),
            Desconto=("Descontos por item", "sum"),
        )
        by_unit["Ticket"] = by_unit["Faturamento"] / by_unit["Notas"].replace(0, np.nan)

        # Merge metas por Unidade
        meta_u = metas.rename(columns={"Objetivo":"Meta"})
        if "Unidade" in meta_u.columns:
            by_unit = by_unit.merge(meta_u[["Unidade","Meta"]], on="Unidade", how="left")
            by_unit["Meta"] = pd.to_numeric(by_unit["Meta"], errors="coerce").fillna(0)
            by_unit["Atingimento"] = np.where(by_unit["Meta"]>0, by_unit["Faturamento"]/by_unit["Meta"], np.nan)
            by_unit["Gap"] = by_unit["Meta"] - by_unit["Faturamento"]

        by_unit = by_unit.sort_values("Faturamento", ascending=False)
        st.dataframe(by_unit, use_container_width=True)

        fig = px.bar(by_unit.head(25), x="Faturamento", y="Unidade", orientation="h", color="Regional")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Coluna 'Unidade' não encontrada.")

# ----------------------------
# Aba Regionais (com meta)
# ----------------------------
with tabs[2]:
    st.subheader("Performance por Regional + Meta (Fev)")
    if "Regional" in df.columns:
        by_reg = df.groupby("Regional", as_index=False).agg(
            Faturamento=("Total Nota", "sum"),
            Notas=("Total Nota", "size"),
            Desconto=("Descontos por item", "sum"),
        )
        by_reg["Ticket"] = by_reg["Faturamento"] / by_reg["Notas"].replace(0, np.nan)

        if "Regional" in metas.columns and "Objetivo" in metas.columns:
            meta_r = metas.groupby("Regional", as_index=False).agg(Meta=("Objetivo","sum"))
            by_reg = by_reg.merge(meta_r, on="Regional", how="left").fillna({"Meta":0})
            by_reg["Atingimento"] = np.where(by_reg["Meta"]>0, by_reg["Faturamento"]/by_reg["Meta"], np.nan)
            by_reg["Gap"] = by_reg["Meta"] - by_reg["Faturamento"]

        by_reg = by_reg.sort_values("Faturamento", ascending=False)
        st.dataframe(by_reg, use_container_width=True)

        fig = px.bar(by_reg, x="Faturamento", y="Regional", orientation="h")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Coluna 'Regional' não encontrada.")

# ----------------------------
# Aba Vendedores
# ----------------------------
with tabs[3]:
    st.subheader("Ranking por Vendedor")
    if "Nome_vendedor" in df.columns:
        by_sell = df.groupby(["Nome_vendedor","Unidade","Regional"], as_index=False).agg(
            Faturamento=("Total Nota","sum"),
            Notas=("Total Nota","size"),
            Desconto=("Descontos por item","sum"),
        )
        by_sell["Ticket"] = by_sell["Faturamento"] / by_sell["Notas"].replace(0, np.nan)
        by_sell = by_sell.sort_values("Faturamento", ascending=False)

        topn = st.slider("Top N", 5, 80, 20)
        st.dataframe(by_sell.head(topn), use_container_width=True)

        fig = px.bar(by_sell.head(topn), x="Faturamento", y="Nome_vendedor", orientation="h", color="Unidade")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Coluna 'Nome_vendedor' não encontrada.")

# ----------------------------
# Aba Estoque ABC + Comportamento Peça (igual DAX)
# ----------------------------
with tabs[4]:
    st.subheader("Estoque ABC (atual + média) com 'Comportamento Peça'")

    # Tipos numéricos
    for c in ["Estoque","MAD"]:
        if c in est_atual.columns:
            est_atual[c] = pd.to_numeric(est_atual[c], errors="coerce")
    if "media_estoque" in est_media.columns:
        est_media["media_estoque"] = pd.to_numeric(est_media["media_estoque"], errors="coerce")

    # Join pelo id_excel
    if "id_excel" not in est_atual.columns or "id_excel" not in est_media.columns:
        st.error("Preciso da coluna 'id_excel' em Sheet1 e em estoque_media para calcular o comportamento.")
        st.stop()

    base = est_atual.merge(est_media[["id_excel","media_estoque"]], on="id_excel", how="left")

    # Implementação igual ao DAX:
    # Limite = MAX(1, Mad*0.20)
    base["Limite"] = np.maximum(1, base["MAD"] * FATOR_COMPORTAMENTO)
    base["Dif"] = base["Estoque"] - base["media_estoque"]

    mask_blank = base["media_estoque"].isna() | base["Estoque"].isna() | base["MAD"].isna()

    base["Comportamento Peça"] = np.select(
        [
            ~mask_blank & (base["Dif"] >  base["Limite"]),
            ~mask_blank & (base["Dif"] < -base["Limite"]),
            ~mask_blank
        ],
        ["▲","▼","▬"],
        default=np.nan
    )

    # Filtro rápido por comportamento
    st.markdown("#### Filtros do Estoque")
    colf1, colf2, colf3 = st.columns(3)

    with colf1:
        opts = ["Todos"] + [x for x in ["▲","▼","▬"] if x in base["Comportamento Peça"].dropna().unique()]
        comp_sel = st.selectbox("Comportamento", opts, index=0)
    with colf2:
        curva_col = "Cód. Curva" if "Cód. Curva" in base.columns else ("Cód. Curva " if "Cód. Curva " in base.columns else None)
        if curva_col:
            curvas = ["Todos"] + sorted(base[curva_col].dropna().unique().tolist())
            curva_sel = st.selectbox("Curva", curvas, index=0)
        else:
            curva_sel = "Todos"
    with colf3:
        empresa_col = "Nome da Empresa" if "Nome da Empresa" in base.columns else None
        if empresa_col:
            empresas = ["Todos"] + sorted(base[empresa_col].dropna().unique().tolist())
            emp_sel = st.selectbox("Empresa", empresas, index=0)
        else:
            emp_sel = "Todos"

    view = base.copy()
    if comp_sel != "Todos":
        view = view[view["Comportamento Peça"] == comp_sel]
    if curva_sel != "Todos" and curva_col:
        view = view[view[curva_col] == curva_sel]
    if emp_sel != "Todos" and empresa_col:
        view = view[view[empresa_col] == emp_sel]

    # Mostra tabela
    cols_show = []
    for c in ["Nome da Empresa","Cód. Item","Descrição","Cód. Curva","Estoque","media_estoque","MAD","Dif","Limite","Comportamento Peça","Ação"]:
        if c in view.columns:
            cols_show.append(c)

    st.dataframe(
        view[cols_show].sort_values(["Comportamento Peça","Dif"], ascending=[True, False]).head(400),
        use_container_width=True
    )

    # Gráfico: contagem por comportamento
    st.markdown("#### Distribuição do Comportamento")
    dist = view["Comportamento Peça"].value_counts(dropna=True).reset_index()
    dist.columns = ["Comportamento", "Qtd Itens"]
    fig = px.bar(dist, x="Comportamento", y="Qtd Itens")
    st.plotly_chart(fig, use_container_width=True)

st.caption("Próximo passo: aplicar essa mesma lógica de 'seta' para Vendas (ex.: MTD vs MTD M-1 ou Projetado vs Meta).")
