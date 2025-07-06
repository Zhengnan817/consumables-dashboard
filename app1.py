import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Consumables Dashboard", layout="wide")

@st.cache_data
def load_data():
    # 1) 从 GitHub Raw 下载历史 Excel
    excel_url = (
        "https://raw.githubusercontent.com/"
        "Zhengnan817/consumables-dashboard/"
        "main/data/2023-2025.xlsx"
    )
    try:
        df_old = pd.read_excel(excel_url, engine="openpyxl")
    except Exception as e:
        st.error(f"加载历史数据失败：{e}")
        return pd.DataFrame()
    df_old.columns = df_old.columns.str.strip()
    df_old["Date"] = pd.to_datetime(df_old["Date"], errors="coerce")
    if "department" in df_old.columns:
        df_old.rename(columns={"department": "Dept"}, inplace=True)

    # 2) 从 GitHub Raw 下载 2025 年 6 月 CSV
    june_url = (
        "https://raw.githubusercontent.com/"
        "Zhengnan817/consumables-dashboard/"
        "main/data/P%20CM%20All%20Trans%20June%202025.csv"
    )
    try:
        df_new = pd.read_csv(june_url)
    except Exception as e:
        st.error(f"加载 6 月数据失败：{e}")
        return pd.DataFrame()
    df_new.columns = df_new.columns.str.strip()
    df_new["Date"] = pd.to_datetime(df_new["Date"], errors="coerce")
    if "Department" in df_new.columns:
        df_new.rename(columns={"Department": "Dept"}, inplace=True)

    # 3) 保留所需字段
    cols = ["Date","Item","Description","Quantity","Price","Extension","Employee.1","Dept"]
    df_old = df_old[[c for c in cols if c in df_old.columns]]
    df_new = df_new[[c for c in cols if c in df_new.columns]]

    # 4) 清洗数值列
    def clean_num(s):
        return pd.to_numeric(
            s.astype(str).str.replace(r"[\$,()]", "", regex=True),
            errors="coerce"
        )
    for df in (df_old, df_new):
        for col in ["Quantity","Price","Extension"]:
            if col in df.columns:
                df[col] = clean_num(df[col])

    # 5) 标准化 Dept 代码
    dept_map = {
        "BTC":"BT","WTC":"WT","IM":"IM","QC AND NDT":"QC",
        "MAINT":"MT","WH":"SCM","LOGI":"SCM"
    }
    for df in (df_old, df_new):
        if "Dept" in df.columns:
            df["Dept"] = df["Dept"].astype(str).str.strip().replace(dept_map)

    # 6) 合并并过滤部门
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df[df["Dept"].isin(["BT","WT","IM","QC","MT","SCM"])]
    return df.dropna(subset=["Date","Quantity","Extension"])

# Load and check
df = load_data()
if df.empty:
    st.stop()

# Page selection
pages = ["Overview", "BT", "WT", "IM", "QC", "MT", "SCM"]
page = st.sidebar.radio("Select View", pages)

df_page = df if page == "Overview" else df[df["Dept"] == page]

# Page title
title = page if page != "Overview" else "Overview"
st.title(title)

# Common KPIs
total_qty = df_page["Quantity"].sum()
total_val = df_page["Extension"].sum()
total_records = df_page.shape[0]
c1, c2, c3 = st.columns(3)
c1.metric("Total Quantity", f"{total_qty:,.0f}")
c2.metric("Total Value ($)", f"{total_val:,.2f}")
c3.metric("Total Records", total_records)

# Overview page
if page == "Overview":
    # 1) Total monthly spending trend (bar + line)
    st.subheader("Total Monthly Spending (2023–2025)")
    colA, colB = st.columns([4, 1])
    with colA:
        mono = df.groupby(df["Date"].dt.to_period("M"))["Extension"].sum().reset_index()
        mono["Date"] = mono["Date"].dt.to_timestamp()
        fig1 = px.bar(mono, x="Date", y="Extension", text_auto='.2s', labels={"Extension": "Spending ($)"})
        fig1.add_scatter(x=mono["Date"], y=mono["Extension"], mode="lines+markers", name="Trend")
        st.plotly_chart(fig1, use_container_width=True)
    with colB:
        years = sorted(df["Date"].dt.year.unique())
        sel_year = st.selectbox("Year", years, index=len(years)-1)

    # 2) Yearly monthly spending
    df_year = df[df["Date"].dt.year == sel_year]
    mon_y = df_year.groupby(df_year["Date"].dt.to_period("M"))["Extension"].sum().reset_index()
    mon_y["Date"] = mon_y["Date"].dt.to_timestamp()
    st.subheader(f"{sel_year} Monthly Spending")
    fig2 = px.bar(mon_y, x="Date", y="Extension", text_auto='.2s', labels={"Extension": "Spending ($)"})
    st.plotly_chart(fig2, use_container_width=True)

    # 3) Department spending latest month
    last_period = df_year["Date"].dt.to_period("M").max()
    df_last = df_year[df_year["Date"].dt.to_period("M") == last_period]
    dp = df_last.groupby("Dept")["Extension"].sum().reset_index()
    st.subheader("Department Spending (Latest Month)")
    fig3 = px.pie(dp, names="Dept", values="Extension", hole=0.2)
    fig3.update_traces(textinfo='percent+label')
    fig3.update_layout(height=500)
    st.plotly_chart(fig3, use_container_width=True)

    # 4) Top 10 Items by Usage & Cost
    top_q = df.groupby("Item")["Quantity"].sum().nlargest(10)
    top_e = df.groupby("Item")["Extension"].sum().nlargest(10)
    top_q.index = [f"{i+1}. {x}" for i, x in enumerate(top_q.index)]
    top_e.index = [f"{i+1}. {x}" for i, x in enumerate(top_e.index)]
    qcol, ecol = st.columns(2)
    with qcol:
        st.subheader("Top 10 Items by Usage")
        fq = px.pie(names=top_q.index, values=top_q.values)
        fq.update_traces(textinfo='percent+label')
        st.plotly_chart(fq, use_container_width=True)
    with ecol:
        st.subheader("Top 10 Items by Cost")
        fe = px.pie(names=top_e.index, values=top_e.values)
        fe.update_traces(textinfo='percent+label')
        st.plotly_chart(fe, use_container_width=True)

# Department-specific pages
else:
    st.subheader(f"{page} Monthly Spending (2023–2025)")
    dept_trend = df_page.groupby(df_page["Date"].dt.to_period("M"))["Extension"].sum().reset_index()
    dept_trend["Date"] = dept_trend["Date"].dt.to_timestamp()
    ftrend = px.bar(dept_trend, x="Date", y="Extension", text_auto='.2s', labels={"Extension": "Spending ($)"})
    ftrend.add_scatter(x=dept_trend["Date"], y=dept_trend["Extension"], mode="lines+markers", name="Trend")
    st.plotly_chart(ftrend, use_container_width=True)

    # Top 10 usage & cost
    top_q = df_page.groupby("Item")["Quantity"].sum().nlargest(10)
    top_e = df_page.groupby("Item")["Extension"].sum().nlargest(10)
    top_q.index = [f"{i+1}. {x}" for i, x in enumerate(top_q.index)]
    top_e.index = [f"{i+1}. {x}" for i, x in enumerate(top_e.index)]
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top 10 Items by Usage")
        fig_u = px.pie(names=top_q.index, values=top_q.values)
        fig_u.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_u, use_container_width=True)
    with c2:
        st.subheader("Top 10 Items by Cost")
        fig_c = px.pie(names=top_e.index, values=top_e.values)
        fig_c.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_c, use_container_width=True)

    # Data table
    st.subheader("Data Table")
    st.dataframe(
        df_page[["Date", "Item", "Description", "Quantity", "Price", "Extension", "Employee.1"]],
        use_container_width=True
    )
