import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Consumables Dashboard", layout="wide")

@st.cache_data
def load_data():
    # Load new data (CSV)
    df_new = pd.read_csv(r"D:\Cedric\Consumables\Power BI\June\Python\P CM All Trans June 2025.csv")
    df_new.columns = df_new.columns.str.strip()
    df_new["Date"] = pd.to_datetime(df_new["Date"], errors="coerce")
    if "Department" in df_new.columns:
        df_new.rename(columns={"Department": "Dept"}, inplace=True)

    # Load old data (Excel)
    df_old = pd.read_excel(r"D:\Cedric\Consumables\Power BI\2023-2025.xlsx", engine="openpyxl")
    df_old.columns = df_old.columns.str.strip()
    df_old["Date"] = pd.to_datetime(df_old["Date"], errors="coerce")
    if "department" in df_old.columns:
        df_old.rename(columns={"department": "Dept"}, inplace=True)

    # Select relevant columns
    cols = ["Date", "Item", "Description", "Quantity", "Price", "Extension", "Employee.1", "Dept"]
    df_old = df_old[[c for c in cols if c in df_old.columns]]
    df_new = df_new[[c for c in cols if c in df_new.columns]]

    # Clean numeric data
    def clean_numeric(s):
        return pd.to_numeric(s.astype(str).str.replace(r"[\$,()]", "", regex=True), errors="coerce")

    for frame in (df_old, df_new):
        for col in ["Quantity", "Price", "Extension"]:
            if col in frame.columns:
                frame[col] = clean_numeric(frame[col])

    # Map departments
    mapping = {
        "BTC": "BT", "IM": "IM", "QC AND NDT": "QC",
        "MAINT": "MT", "WTC": "WT", "WH": "SCM", "LOGI": "SCM"
    }
    for frame in (df_old, df_new):
        frame["Dept"] = frame["Dept"].map(mapping).fillna(frame["Dept"])

    # Combine and filter
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df[df["Dept"].isin(["BT", "WT", "IM", "QC", "MT", "SCM"])]
    return df.dropna(subset=["Date", "Quantity", "Extension"])

# Load data
df = load_data()



# Page selection
pages = ["Overview", "BT", "WT", "IM", "QC", "MT", "SCM"]
page = st.sidebar.radio("Select View", pages)

# Filter dataframe for the selected page
if page != "Overview":
    df_page = df[df["Dept"] == page]
else:
    df_page = df

st.title(page)

# Common KPIs for each page
total_qty = df_page["Quantity"].sum()
total_value = df_page["Extension"].sum()
total_records = df_page.shape[0]
col1, col2, col3 = st.columns(3)
col1.metric("Total Quantity", f"{total_qty:,.0f}")
col2.metric("Total Value ($)", f"{total_value:,.2f}")
col3.metric("Total Records", total_records)

# Overview page
if page == "Overview":
    # 1. Total monthly spending 2023-2025 with filter on same line
    st.subheader("Total Monthly Spending (2023-2025)")
    colA, colB = st.columns([4,1])
    with colA:
        monthly_all = df.groupby(df["Date"].dt.to_period("M"))["Extension"].sum().reset_index()
        monthly_all["Date"] = monthly_all["Date"].dt.to_timestamp()
        fig1 = px.bar(monthly_all, x="Date", y="Extension", text_auto='.2s')
        fig1.add_scatter(x=monthly_all["Date"], y=monthly_all["Extension"], mode="lines+markers", name="Trend")
        fig1.update_layout(yaxis_title="Spending ($)")
        st.plotly_chart(fig1, use_container_width=True)
    with colB:
        years = sorted(df["Date"].dt.year.unique())
        selected_year = st.selectbox("Year", years, index=len(years)-1, key="yr")

    # 2. Yearly monthly spending
    df_year = df[df["Date"].dt.year == selected_year]
    m = df_year.groupby(df_year["Date"].dt.to_period("M"))["Extension"].sum().reset_index()
    m["Date"] = m["Date"].dt.to_timestamp()
    st.subheader(f"{selected_year} Monthly Spending")
    fig2 = px.bar(m, x="Date", y="Extension", text_auto='.2s')
    fig2.update_layout(yaxis_title="Spending ($)")
    st.plotly_chart(fig2, use_container_width=True)

    # 3. Latest month department pie
    # 3. Latest‐month department pie, within the selected year
    last_period = df_year["Date"].dt.to_period("M").max()
    last_df    = df_year[df_year["Date"].dt.to_period("M") == last_period]
    dp         = last_df.groupby("Dept")["Extension"].sum().reset_index()

    st.subheader("Department Spending (Latest Month)")
    fig3 = px.pie(dp, names="Dept", values="Extension", hole=0.2)
    fig3.update_traces(textinfo='percent+label')
    fig3.update_layout(height=500)
    st.plotly_chart(fig3, use_container_width=True)

    # 4 & 5. Top 10 usage & cost pies side-by-side
    col1, col2 = st.columns(2)
    tu = df.groupby("Item")["Quantity"].sum().nlargest(10)
    tc = df.groupby("Item")["Extension"].sum().nlargest(10)
    tu.index = [f"{i+1}. {x}" for i, x in enumerate(tu.index)]
    tc.index = [f"{i+1}. {x}" for i, x in enumerate(tc.index)]
    with col1:
        st.subheader("Top 10 Items by Usage")
        fig4 = px.pie(names=tu.index, values=tu.values)
        fig4.update_traces(textinfo='percent+label')
        st.plotly_chart(fig4, use_container_width=True)
    with col2:
        st.subheader("Top 10 Items by Cost")
        fig5 = px.pie(names=tc.index, values=tc.values)
        fig5.update_traces(textinfo='percent+label')
        st.plotly_chart(fig5, use_container_width=True)

# Department-specific pages
else:
    t = df_page.groupby(df_page["Date"].dt.to_period("M"))["Extension"].sum().reset_index()
    t["Date"] = t["Date"].dt.to_timestamp()
    st.subheader(f"{page} Monthly Spending (2023-2025)")
    fig = px.bar(t, x="Date", y="Extension", text_auto='.2s')
    fig.add_scatter(x=t["Date"], y=t["Extension"], mode="lines+markers", name="Trend")
    fig.update_layout(yaxis_title="Spending ($)")
    st.plotly_chart(fig, use_container_width=True)

    # Top 10 usage & cost pies
    tu = df_page.groupby("Item")["Quantity"].sum().nlargest(10)
    tc = df_page.groupby("Item")["Extension"].sum().nlargest(10)
    tu.index = [f"{i+1}. {x}" for i, x in enumerate(tu.index)]
    tc.index = [f"{i+1}. {x}" for i, x in enumerate(tc.index)]
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top 10 Items by Usage")
        fig_u = px.pie(names=tu.index, values=tu.values)
        fig_u.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_u, use_container_width=True)
    with c2:
        st.subheader("Top 10 Items by Cost")
        fig_c = px.pie(names=tc.index, values=tc.values)
        fig_c.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_c, use_container_width=True)

    st.subheader("Data Table")
    st.dataframe(df_page[["Date", "Item", "Description", "Quantity", "Price", "Extension", "Employee.1"]], use_container_width=True)
