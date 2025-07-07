import os
import pandas as pd
import streamlit as st
import plotly.express as px
import requests
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans



st.set_page_config(page_title="Oliver Van Horn Consumables Dashboard", layout="wide")

st.markdown(
    """
    <style>
      /* Metrics: larger label & value */
      .stMetric .label { font-size: 4.5rem !important; }
      .stMetric .value { font-size: 5.5rem !important; }

      /* Tabs: larger font */
      button[data-baseweb="tab"] span {
        font-size: 4.25rem !important;
      }
    </style>
    """,
    unsafe_allow_html=True
)
# — Logo & Main Title —
st.image(
    "https://raw.githubusercontent.com/Zhengnan817/consumables-dashboard/main/resource/cswind%20logo.png",
    width=180,
)
st.markdown("""
# Oliver Van Horn Consumables Dashboard  
*Interactive analysis of consumables usage & spend across departments*  

---
""")


@st.cache_data
def load_data():
    # 1) 读取历史 Excel（GitHub raw）
    excel_url = (
        "https://raw.githubusercontent.com/"
        "Zhengnan817/consumables-dashboard/"
        "main/data/2023-2025.xlsx"
    )
    try:
        df_old = pd.read_excel(excel_url, engine="openpyxl")
    except Exception as e:
        st.error(f"❗ loading histrocial Excel Failed：{e}")
        return pd.DataFrame()
    df_old.columns = df_old.columns.str.strip()
    df_old["Date"] = pd.to_datetime(df_old["Date"], errors="coerce")
    # 兼容 Department 列
    for col in ("department","Department"):
        if col in df_old.columns:
            df_old.rename(columns={col: "Dept"}, inplace=True)
            break

    # 2) 调用 GitHub API 列出 data/monthly 下的所有文件
    api_url = (
        "https://api.github.com/repos/"
        "Zhengnan817/consumables-dashboard/"
        "contents/data/monthly"
    )
    try:
        files = requests.get(api_url).json()
    except Exception as e:
        st.error(f"❗ GitHub API 调用失败：{e}")
        return pd.DataFrame()

    # 3) 筛出所有 .csv 并用 download_url 读取
    df_new_list = []
    for f in files:
        if f.get("type") == "file" and f.get("name","").lower().endswith(".csv"):
            url = f["download_url"]
            try:
                df = pd.read_csv(url)
            except Exception as e:
                st.error(f"❗ 加载 CSV {f['name']} 失败：{e}")
                continue
            df.columns = df.columns.str.strip()
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            if "Department" in df.columns:
                df.rename(columns={"Department": "Dept"}, inplace=True)
            df_new_list.append(df)

    if not df_new_list:
        st.error("❗ 没有找到任何 CSV 文件")
        return pd.DataFrame()
    df_new = pd.concat(df_new_list, ignore_index=True)

    # 4) 保留字段
    keep = ["Date","Item","Description","Quantity","Price","Extension","Employee.1","Dept"]
    df_old = df_old[[c for c in keep if c in df_old.columns]]
    df_new = df_new[[c for c in keep if c in df_new.columns]]

    # 5) 数值清洗
    def clean_num(s):
        return pd.to_numeric(
            s.astype(str).str.replace(r"[\$,()]", "", regex=True),
            errors="coerce"
        )
    for frame in (df_old, df_new):
        for col in ("Quantity","Price","Extension"):
            if col in frame.columns:
                frame[col] = clean_num(frame[col])

    # 6) 标准化 Dept
    dept_map = {
        "BTC":"BT","WTC":"WT","IM":"IM","QC AND NDT":"QC",
        "MAINT":"MT","WH":"SCM","LOGI":"SCM"
    }
    for frame in (df_old, df_new):
        if "Dept" in frame.columns:
            frame["Dept"] = (
                frame["Dept"].astype(str)
                         .str.strip()
                         .replace(dept_map)
            )

    # 7) 合并 & 保留所有记录（包含 Extension 和 Dept 的空值）
    # df = pd.concat([df_old, df_new], ignore_index=True)
    # df = df.dropna(subset=["Date", "Quantity"])  # 只过滤日期和数量，保留 Extension 和 Dept 空值
    # return df
    # 7) 合并 & 过滤
    df = pd.concat([df_old, df_new], ignore_index=True)

    # 排除无效或非目标部门数据
    exclude_depts = [
        "KONE,CRANE PUEBLO",
        "Portugal,Employee",
        "Pueblo,HSE",
        "Pueblo,Kitting"
    ]
    df = df[~df["Dept"].isin(exclude_depts)]
    return df.dropna(subset=["Date", "Quantity"])


# Load data
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

# Common KPIs（包含所有 Extension 值，空值视为0）
total_qty = df_page["Quantity"].fillna(0).sum()
total_val = df_page["Extension"].fillna(0).sum()
total_records = df_page.shape[0]

# Display metrics
c1, c2, c3 = st.columns(3)
c1.metric("Total Value ($)", f"{total_val:,.2f}")
c2.metric("Total Quantity", f"{total_qty:,.0f}")
c3.metric("Total Records", total_records)

# ⚠️ 备注说明空值处理
if df_page["Extension"].isna().sum() > 0:
    st.caption("⚠️ Note: Some records are missing cost data (Extension). These are treated as $0 in totals.")




if page == "Overview":
    # prepare data for all charts
    mono = (
    df
    .groupby(df["Date"].dt.to_period("M"), dropna=False)["Extension"]
    .sum(min_count=1)  # 保留空值记录
    .reset_index()
    )
    mono["Date"] = mono["Date"].dt.to_timestamp()
    years = sorted(df["Date"].dt.year.unique())
    default_year = years[-1]
    df_year = df[df["Date"].dt.year == default_year]
    monthly = (
        df_year
        .groupby(df_year["Date"].dt.to_period("M"))["Extension"]
        .sum()
        .reset_index()
    )
    monthly["Date"] = monthly["Date"].dt.to_timestamp()
    last_period = df_year["Date"].dt.to_period("M").max()
    df_last = df_year[df_year["Date"].dt.to_period("M") == last_period]

    # top 10 all-time
    top_q = (
    df.groupby("Item")["Quantity"]
    .sum(min_count=1)
    .nlargest(10)
    )
    top_e = (
        df.groupby("Item")["Extension"]
        .sum(min_count=1)
        .nlargest(10)
    )

    top_q.index = [f"{i+1}. {item}" for i, item in enumerate(top_q.index)]
    top_e.index = [f"{i+1}. {item}" for i, item in enumerate(top_e.index)]

    # build figures
    fig_all = px.bar(
        mono, x="Date", y="Extension", text_auto=".2s",
        labels={"Extension": "Spending ($)"}
    )
    fig_all.add_scatter(
        x=mono["Date"], y=mono["Extension"],
        mode="lines+markers", name="Trend"
    )

    fig_year = px.bar(
        monthly, x="Date", y="Extension", text_auto=".2s",
        labels={"Extension": "Spending ($)"}
    )

    dp = (
    df_last
    .groupby("Dept", dropna=False)["Extension"]
    .sum(min_count=1)
    .reset_index()
    )
    dp["Dept"] = dp["Dept"].fillna("Unassigned")  # 填充空值标签
    fig_dep = px.pie(
        dp, names="Dept", values="Extension", hole=0.2
    )

    fig_dep = px.pie(
        dp, names="Dept", values="Extension", hole=0.2
    )
    fig_dep.update_traces(textinfo="percent+label")
    fig_dep.update_layout(height=500)

    fig_u = px.pie(names=top_q.index, values=top_q.values)
    fig_u.update_traces(textinfo="percent+label")
    fig_c = px.pie(names=top_e.index, values=top_e.values)
    fig_c.update_traces(textinfo="percent+label")

    # render as tabs
    tabs = st.tabs(["Trend", "By Year", "Dept Share", "Top Items"])

    with tabs[0]:
        st.header("Overall 2023–2025 Trend")
        st.plotly_chart(fig_all, use_container_width=True)

    with tabs[1]:
        st.header(f"{default_year} Monthly Spending")
        sel_year = st.selectbox("Year", years, index=len(years) - 1)
        # update yearly chart if user selects a different year
        df_year = df[df["Date"].dt.year == sel_year]
        monthly = (
            df_year
            .groupby(df_year["Date"].dt.to_period("M"))["Extension"]
            .sum()
            .reset_index()
        )
        monthly["Date"] = monthly["Date"].dt.to_timestamp()
        fig_year = px.bar(
            monthly, x="Date", y="Extension", text_auto=".2s",
            labels={"Extension": "Spending ($)"}
        )
        st.plotly_chart(fig_year, use_container_width=True)

    with tabs[2]:
        month_label = last_period.to_timestamp().strftime("%B %Y")
        st.header(f"Dept Spending Comparison — Overall vs {month_label}")

        # 计算 Overall（总时间段）部门支出
        dept_overall = (
            df[df["Dept"].notna()]
            .groupby("Dept")["Extension"]
            .sum()
            .reset_index()
        )
        fig_dep_overall = px.pie(
            dept_overall, names="Dept", values="Extension", hole=0.2
        )
        fig_dep_overall.update_traces(textinfo="percent+label")
        fig_dep_overall.update_layout(height=500)

        # 当前月 Pie Chart 已在前面定义为 fig_dep
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Overall (2023–2025)")
            st.plotly_chart(fig_dep_overall, use_container_width=True)

        with col2:
            st.subheader(f"{month_label}")
            st.plotly_chart(fig_dep, use_container_width=True)

    with tabs[3]:
        st.header("Top 10 Items")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("By Usage")
            st.plotly_chart(fig_u, use_container_width=True)
        with c2:
            st.subheader("By Cost")
            st.plotly_chart(fig_c, use_container_width=True)




# Department-specific pages
else:
    # 1) overall trend
    dept_trend = (
        df_page
        .groupby(df_page["Date"].dt.to_period("M"))["Extension"]
        .sum()
        .reset_index()
    )
    dept_trend["Date"] = dept_trend["Date"].dt.to_timestamp()
    fig_trend = px.bar(
        dept_trend,
        x="Date", y="Extension",
        text_auto=".2s",
        labels={"Extension":"Spending ($)"}
    )
    fig_trend.add_scatter(
        x=dept_trend["Date"],
        y=dept_trend["Extension"],
        mode="lines+markers",
        name="Trend"
    )

    # 2) all-time top-10 items
    top_q = df_page.groupby("Item")["Quantity"].sum().nlargest(10)
    top_e = df_page.groupby("Item")["Extension"].sum().nlargest(10)
    top_q.index = [f"{i+1}. {item}" for i,item in enumerate(top_q.index)]
    top_e.index = [f"{i+1}. {item}" for i,item in enumerate(top_e.index)]
    fig_q = px.pie(names=top_q.index, values=top_q.values)
    fig_q.update_traces(textinfo="percent+label")
    fig_e = px.pie(names=top_e.index, values=top_e.values)
    fig_e.update_traces(textinfo="percent+label")

    # 3) latest-month top-10 items
    last_period = df_page["Date"].dt.to_period("M").max()
    month_label = last_period.to_timestamp().strftime("%B %Y")
    df_last = df_page[df_page["Date"].dt.to_period("M") == last_period]
    top_q_last = df_last.groupby("Item")["Quantity"].sum().nlargest(10)
    top_e_last = df_last.groupby("Item")["Extension"].sum().nlargest(10)
    top_q_last.index = [f"{i+1}. {item}" for i,item in enumerate(top_q_last.index)]
    top_e_last.index = [f"{i+1}. {item}" for i,item in enumerate(top_e_last.index)]
    fig_qm = px.pie(names=top_q_last.index, values=top_q_last.values)
    fig_qm.update_traces(textinfo="percent+label")
    fig_em = px.pie(names=top_e_last.index, values=top_e_last.values)
    fig_em.update_traces(textinfo="percent+label")


    # 5) 当月每个员工的总消费
        # 5) 当月每个员工的总消费 & 异常检测
    df_em = df_page[df_page["Date"].dt.to_period("M") == last_period]
    emp_spend = (
        df_em
        .groupby("Employee.1")["Extension"]
        .sum()
        .reset_index(name="Total_Spend")
    )
    # 过滤掉无效行
    emp_spend = emp_spend[emp_spend["Total_Spend"] > 0]

    if not emp_spend.empty:
        from sklearn.ensemble import IsolationForest
        iso = IsolationForest(contamination=0.05, random_state=42)
        emp_spend["anomaly_flag"] = iso.fit_predict(emp_spend[["Total_Spend"]])
        emp_spend["Anomaly"] = emp_spend["anomaly_flag"] == -1

        # 只保留异常员工
        anomalies = emp_spend[emp_spend["Anomaly"]]

        # 准备画图
        fig_emp = px.bar(
            anomalies.sort_values("Total_Spend"),
            x="Total_Spend",
            y="Employee.1",
            orientation="h",
            text="Total_Spend",
            color="Total_Spend",              # 你也可以只用大小编码
            labels={"Total_Spend":"Spend ($)", "Employee.1":"Employee"},
            title=f"🚩 Anomalous Spenders — {month_label}"
        )
        fig_emp.update_layout(yaxis={"categoryorder":"total ascending"})
    else:
        anomalies = pd.DataFrame()  # 为空

# Prepare employee features for clustering
    df_em = df_page[df_page["Date"].dt.to_period("M") == last_period]
    emp_feats = (
        df_em
        .groupby("Employee.1")
        .agg(
            Total_Spend=("Extension", "sum"),
            Txn_Count=("Extension", "count")
        )
        .reset_index()
    )

    # Only keep employees with nonzero activity
    emp_feats = emp_feats[(emp_feats["Total_Spend"] > 0) & (emp_feats["Txn_Count"] > 0)]

    # Run KMeans to identify 3 clusters
        # Run KMeans …
    kmeans = KMeans(n_clusters=3, random_state=42).fit(emp_feats[["Total_Spend","Txn_Count"]])
    emp_feats["Cluster"] = kmeans.labels_.astype(str)

    # ──> Insert friendly‐label mapping here:
    # 1) compute centroid summary
    centroids = pd.DataFrame(
        kmeans.cluster_centers_,
        columns=["Total_Spend","Txn_Count"]
    ).assign(Cluster=lambda df: df.index.astype(str))

    # 2) pick extremes
    hf_ls = (
        centroids
        .sort_values(["Txn_Count","Total_Spend"], ascending=[False,True])
        .iloc[0]["Cluster"]
    )
    lf_hs = (
        centroids
        .sort_values(["Txn_Count","Total_Spend"], ascending=[True,False])
        .iloc[0]["Cluster"]
    )

    # 3) build label map (others → mid‐range)
    label_map = {
        hf_ls: "High-Freq, Low-Spend",
        lf_hs: "Low-Freq, High-Spend"
    }
    for c in emp_feats["Cluster"].unique():
        if c not in label_map:
            label_map[c] = "Mid-Range"

    # 4) apply it
    emp_feats["Cluster_Label"] = emp_feats["Cluster"].map(label_map)

    # ──> now build fig_cluster using “Cluster_Label” instead of raw “Cluster”:
    fig_cluster = px.scatter(
        emp_feats,
        x="Txn_Count",
        y="Total_Spend",
        color="Cluster_Label",               # ← use friendly labels
        hover_data=["Employee.1"],
        labels={
            "Txn_Count":    "Transaction Count",
            "Total_Spend":   "Total Spend ($)",
            "Cluster_Label":"Segment"
        },
        title=f"Employee Clusters — {last_period.strftime('%B %Y')}"
    )
    fig_cluster.update_layout(legend_title_text="Segment")

    lowfreq_highspend_cluster = (
    centroids
    .sort_values(["Txn_Count", "Total_Spend"], ascending=[True, False])
    .iloc[0]["Cluster"]
    )
    centroids = pd.DataFrame(
    kmeans.cluster_centers_,
    columns=["Total_Spend", "Txn_Count"]
    ).assign(Cluster=lambda d: d.index.astype(str))

    # Sort by Txn_Count descending, then by Total_Spend ascending
    highfreq_lowspend_cluster = (
        centroids
        .sort_values(["Txn_Count", "Total_Spend"], ascending=[False, True])
        .iloc[0]["Cluster"]
    )
    # Get employee lists
    highfreq = emp_feats[emp_feats["Cluster"] == highfreq_lowspend_cluster]["Employee.1"]
    lowfreq  = emp_feats[emp_feats["Cluster"] == lowfreq_highspend_cluster]["Employee.1"]


    # 6) raw data table for anomalies only
    table_df = anomalies.rename(
        columns={"Employee.1": "Employee", "Total_Spend": "Spend ($)"}
    )

    



    # render tabs
    tabs = st.tabs([
    "Trend",
    "All-Time Top Items",
    f"Top Items ({month_label})",
    "Anomalies",
    "Clustering"
    ])

    with tabs[0]:
        st.header(f"{page} Trend (2023–2025)")
        st.plotly_chart(fig_trend, use_container_width=True)

    with tabs[1]:
        st.header(f"{page} All-Time Top 10 Items")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("By Usage")
            st.plotly_chart(fig_q, use_container_width=True)
        with c2:
            st.subheader("By Cost")
            st.plotly_chart(fig_e, use_container_width=True)

    with tabs[2]:
        st.header(f"{page} Top 10 Items — {month_label}")
        c3, c4 = st.columns(2)
        with c3:
            st.subheader("By Usage")
            st.plotly_chart(fig_qm, use_container_width=True)
        with c4:
            st.subheader("By Cost")
            st.plotly_chart(fig_em, use_container_width=True)

    with tabs[3]:
        st.header(f"Employee Anomalies & Spend Table — {last_period.to_timestamp().strftime('%B %Y')}")

        # Human-friendly explanation
        st.markdown(
            """
            **How these anomalies are identified**  
            • We use an Isolation Forest from machine learning, an automated method that spots employees whose monthly spend  
            stands out from the rest.  
            • “Anomalous” here is relative—if someone’s total spend is much higher than peers,  
            the model flags them.  

            **Please note:**  
            This is just a *reference*—department managers should review each flagged employee  
            in context (role, projects, seasonality) to decide whether the spend truly requires action. The spending might be reasonable.
            """
        )

        if not anomalies.empty:
            st.plotly_chart(fig_emp, use_container_width=True)
            st.dataframe(table_df, use_container_width=True)
        else:
            st.info("No anomalous spenders detected for this month.")

    with tabs[4]:
        # Example
        last_period = df_page["Date"].dt.to_period("M").max()
        st.header(f"Employee Clustering — {last_period.to_timestamp().strftime('%B %Y')}")

        
        st.markdown(
            """
            We’ve clustered each employee by transaction count vs. total spend.
            Below are the two “extreme” groups:
            - **High-Frequency, Low-Spend**: many small transactions  
            - **Low-Frequency, High-Spend**: few large transactions
            """
        )
        st.plotly_chart(fig_cluster, use_container_width=True)

        st.subheader("High-Frequency, Low-Spend — Purchase Details (>$200 & >5 transactions)")

        # 获取属于高频低额群体的员工消费记录
        df_high_items = df_em[df_em["Employee.1"].isin(highfreq)]

        # 聚合数据：每位员工对每个物品的消费频次与金额
        high_details = (
            df_high_items
            .groupby(["Employee.1", "Item"])
            .agg(
                Quantity=("Quantity", "sum"),
                Total_Spend=("Extension", "sum"),
                Txn_Count=("Extension", "count")
            )
            .reset_index()
        )

        # 筛选金额 > 200 且频次 > 5 的记录
        filtered_high = high_details.query("Total_Spend > 200 and Txn_Count > 5")

        # 按金额排序
        filtered_high = filtered_high.sort_values("Total_Spend", ascending=False)

        # 展示表格
        st.dataframe(
            filtered_high.rename(columns={
                "Employee.1": "Employee",
                "Item": "Item",
                "Quantity": "Quantity",
                "Txn_Count": "Transaction Count",
                "Total_Spend": "Spend ($)"
            }),
            use_container_width=True
        )


