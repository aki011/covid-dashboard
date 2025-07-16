# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# 0️⃣ ───────── PAGE CONFIG & FONT ───────────────────────────────────────────
st.set_page_config(page_title="COVID‑19 Dashboard", page_icon="🦠", layout="wide")

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
        html, body, [class*="css"]  { font-family: 'Poppins', sans-serif !important; }
        h1, h2, h3, h4 { font-weight: 600; letter-spacing: 0.5px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# 1️⃣ ───────── DATA LOADER (cached) ─────────────────────────────────────────
@st.cache_data(show_spinner=True)
def load_covid_data():
    base = Path("csse_covid_19_data")
    def melt_csv(name, val):
        wide = pd.read_csv(base / name)
        long = wide.melt(
            id_vars=["Province/State","Country/Region","Lat","Long"],
            var_name="date",
            value_name=val,
        )
        long["date"] = pd.to_datetime(long["date"])
        return long

    confirmed = melt_csv("time_series_covid19_confirmed_global.csv","confirmed")
    deaths    = melt_csv("time_series_covid19_deaths_global.csv",   "deaths")
    recovered = melt_csv("time_series_covid19_recovered_global.csv","recovered")

    df = confirmed.merge(deaths, on=["Province/State","Country/Region","Lat","Long","date"])\
                  .merge(recovered,on=["Province/State","Country/Region","Lat","Long","date"])
    df["active"] = df["confirmed"] - df["deaths"] - df["recovered"]
    return df

df = load_covid_data()

# 2️⃣ ───────── SIDEBAR ──────────────────────────────────────────────────────
st.sidebar.title("⚙️ Controls")

countries = sorted(df["Country/Region"].unique())
default_countries = [c for c in ["India", "US"] if c in countries]
selected_countries = st.sidebar.multiselect(
    "🌍 Countries",
    countries,
    default=default_countries or countries[:1],
)

all_metrics = {
    "📈 Confirmed": "confirmed",
    "🟥 Deaths": "deaths",
    "🟩 Recovered": "recovered",
    "🟦 Active": "active",
}
metric_label = st.sidebar.radio("Metric", list(all_metrics.keys()), index=0)
metric = all_metrics[metric_label]

daily_view = st.sidebar.checkbox("Show Daily Changes (diff)", value=False)

min_dt, max_dt = df["date"].min().to_pydatetime(), df["date"].max().to_pydatetime()
date_range = st.sidebar.slider("Date Range", min_value=min_dt, max_value=max_dt, value=(min_dt, max_dt))

# 3️⃣ ───────── FILTERED DATA ───────────────────────────────────────────────
mask = (
    (df["Country/Region"].isin(selected_countries)) &
    (df["date"].between(pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])))
)
plot_df = df[mask].groupby(["date","Country/Region"])[list(all_metrics.values())].sum().reset_index()

if daily_view:
    plot_df = plot_df.sort_values("date")
    plot_df[metric] = plot_df.groupby("Country/Region")[metric].diff().fillna(0)

# 4️⃣ ───────── HEADER & GLOBAL SUMMARY ─────────────────────────────────────
st.title("🦠 Global COVID‑19 Dashboard")

latest = df[df["date"] == df["date"].max()].groupby("Country/Region")[list(all_metrics.values())].sum()
totals = latest.sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Confirmed", f"{int(totals['confirmed']):,}")
c2.metric("Deaths",    f"{int(totals['deaths']):,}")
c3.metric("Recovered", f"{int(totals['recovered']):,}")
c4.metric("Active",    f"{int(totals['active']):,}")

st.markdown("---")

# 5️⃣ ───────── LINE CHART ──────────────────────────────────────────────────
line_fig = px.line(
    plot_df,
    x="date",
    y=metric,
    color="Country/Region",
    title=f"{metric_label.split()[1]} – {'Daily' if daily_view else 'Cumulative'}",
    labels={"date":"Date", "Country/Region":"Country", metric:"Cases"},
)
line_fig.update_layout(hovermode="x unified")
st.plotly_chart(line_fig, use_container_width=True)


# 🔸 helper: always give latest cumulative totals
def latest_totals(df_cumulative):
    return (
        df_cumulative[df_cumulative["date"] == df_cumulative["date"].max()]
        .groupby("Country/Region")[list(all_metrics.values())]
        .sum()
    )

# ...

if daily_view:
    # keep daily diff for the LINE plot only
    plot_df = plot_df.sort_values("date")
    plot_df[metric] = plot_df.groupby("Country/Region")[metric].diff().fillna(0)

# ---- LINE CHART (unchanged) ----
# ...
def last_nonzero_snapshot(df_cum, metric_name):
    """
    Return a snapshot of the data on the most recent date where
    the selected metric has non-zero values.
    """
    for date in sorted(df_cum["date"].unique(), reverse=True):
        snapshot = df_cum[df_cum["date"] == date]
        if snapshot[metric_name].sum() > 0:
            return snapshot, date
    # fallback if all zero
    fallback = df_cum[df_cum["date"] == df_cum["date"].min()]
    return fallback, fallback["date"].iloc[0]



# ---- TOP‑10 BAR CHART (always cumulative) ----
with st.expander("🏆 Top 10 Countries by Metric", expanded=False):
    snap_df, snap_date = last_nonzero_snapshot(df, metric)
    top_latest = (
        snap_df.groupby("Country/Region")[[metric]]
        .sum()
        .sort_values(by=metric, ascending=False)
        .head(10)
        .reset_index()
    )

    bar_fig = px.bar(
        top_latest,
        x=metric,
        y="Country/Region",
        orientation="h",
        text_auto=".2s",
        title=f"Top 10 Countries – {metric.capitalize()} (as of {snap_date.date()})",
    )
    bar_fig.update_layout(yaxis=dict(categoryorder="total ascending"))
    st.plotly_chart(bar_fig, use_container_width=True)


# 7️⃣ ───────── OPTIONAL WORLD MAP ──────────────────────────────────────────
with st.expander("🌍 Show World Map", expanded=False):
    map_fig = px.choropleth(
        latest.reset_index(),
        locations="Country/Region",
        locationmode="country names",
        color=metric,
        color_continuous_scale="Reds",
        title=f"{metric_label.split()[1]} on {df['date'].max().date()}",
    )
    st.plotly_chart(map_fig, use_container_width=True)

# 8️⃣ ───────── CSV DOWNLOAD BUTTON ─────────────────────────────────────────
csv_data = plot_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download filtered data (CSV)",
    data=csv_data,
    file_name="covid_filtered_data.csv",
    mime="text/csv",
)

# 9️⃣ ───────── FOOTER ──────────────────────────────────────────────────────
st.caption("Data: Johns‑Hopkins CSSE • Dashboard by Akshay Makhija")
   