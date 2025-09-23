import io
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

# ---------- Page Setup ----------
st.set_page_config(
    page_title="On-Time Arrival Report",
    page_icon="✅",
    layout="wide"
)

st.title("On-Time Arrival Report")
st.caption("Upload your Excel → choose filters → see on-time performance by carrier")

# ---------- Helpers ----------
EXPECTED_COLUMNS = {
    # left side = our internal key ; right side = expected user column name (case/space tolerant)
    "stop_type": "Stop type",
    "stop_name": "Stop name",
    "stop_city": "Stop city",
    "stop_state": "Stop state",
    "stop_country": "Stop country",
    "planned_arrival_start": "Stop planned arrival time start",
    "planned_arrival_end": "Stop planned arrival time end",
    "actual_arrival": "Stop actual arrival time",
    "arrival_delta_min": "Stop arrival delta (minutes)",
    "actual_departure": "Stop actual departure time",
    "shipment_id": "Shipment ID",
    "shipment_type": "Shipment type",
    "current_state": "Current state",
    "current_state_reason": "Current state reason",
    "latest_milestone_type": "Latest milestone type",
    "latest_milestone_time": "Latest milestone time",
    "exceptions": "Exceptions",
    "open_tasks": "Open tasks",
    "current_carrier": "Current carrier",
    "vessel_built_in": "Vessel details - built in",
    "vessel_used_during": "Vessel details - used during",
    "origin": "Origin",
    "origin_city": "Origin city",
    "origin_state": "Origin state",
    "origin_country": "Origin country",
    "destination": "Destination",
    "destination_city": "Destination city",
    "destination_state": "Destination state",
    "destination_country": "Destination country",
    "dest_eta": "Destination estimated arrival time",
    "dest_actual_arrival": "Destination actual arrival time",
    "dest_initial_planned_start": "Destination initial planned arrival time",
    "dest_initial_planned_end": "Destination initial planned arrival end time",
    "dest_latest_planned_start": "Destination latest planned arrival time",
    "dest_latest_planned_end": "Destination latest planned arrival end time",
    "related_orders": "Related orders",
    "created_time": "Created time",
    "msid": "MSID",
}

DATETIME_KEYS = {
    "planned_arrival_start",
    "planned_arrival_end",
    "actual_arrival",
    "actual_departure",
    "latest_milestone_time",
    "dest_eta",
    "dest_actual_arrival",
    "dest_initial_planned_start",
    "dest_initial_planned_end",
    "dest_latest_planned_start",
    "dest_latest_planned_end",
    "created_time",
}

REQUIRED_FOR_REPORT = {
    "stop_name",
    "planned_arrival_start",
    "actual_arrival",
    "arrival_delta_min",  # preferred, but we will compute if missing
    "current_carrier",
    "created_time",
}

def normalize_columns(cols):
    # Lowercase + strip spaces for matching; keep original to map back
    norm = {c: " ".join(str(c).strip().split()).lower() for c in cols}
    return norm

def build_column_map(df_columns):
    norm = normalize_columns(df_columns)
    rev = {v: k for k, v in norm.items()}
    col_map = {}
    for key, expected_label in EXPECTED_COLUMNS.items():
        look_for = " ".join(expected_label.strip().split()).lower()
        if look_for in rev:
            col_map[key] = rev[look_for]
    return col_map

def to_datetime(series):
    return pd.to_datetime(series, errors="coerce")

@st.cache_data(show_spinner=False)
def read_excel(file_bytes) -> pd.DataFrame:
    return pd.read_excel(file_bytes, engine="openpyxl")

def compute_arrival_delta_minutes(row):
    # Fallback when explicit 'Stop arrival delta (minutes)' is missing
    try:
        a = row["actual_arrival"]
        p = row["planned_arrival_start"]
        if pd.notna(a) and pd.notna(p):
            return (a - p).total_seconds() / 60.0
    except Exception:
        pass
    return np.nan

def apply_on_time_rule(delta_minutes, threshold_minutes):
    # on-time if 'minutes late' <= threshold
    # Negative values (early) are always on-time
    if pd.isna(delta_minutes):
        return np.nan
    return delta_minutes <= threshold_minutes

# ---------- Sidebar: File upload ----------
with st.sidebar:
    st.header("1) Upload Excel")
    uploaded = st.file_uploader("Choose an .xlsx file", type=["xlsx"])

    st.markdown(
        """
        **Notes**
        - All timestamps are treated as the **same timezone** (as per your data).
        - If **Stop arrival delta (minutes)** is missing, the app computes it from
          *Stop actual arrival time* − *Stop planned arrival time start*.
        """
    )

if uploaded is None:
    st.info("⬅️ Upload your Excel file in the sidebar to begin.")
    st.stop()

# ---------- Load & validate ----------
try:
    df_raw = read_excel(uploaded)
except Exception as e:
    st.error(f"Could not read Excel: {e}")
    st.stop()

if df_raw.empty:
    st.warning("The uploaded Excel appears to be empty.")
    st.stop()

col_map = build_column_map(df_raw.columns)
missing_for_report = [EXPECTED_COLUMNS[k] for k in REQUIRED_FOR_REPORT if k not in col_map]
# 'arrival_delta_min' is preferred but we can compute, so don't hard-stop if it's missing.
if "arrival_delta_min" in missing_for_report and all(
    k in col_map for k in ["planned_arrival_start", "actual_arrival"]
):
    missing_for_report.remove("Stop arrival delta (minutes)")

if missing_for_report:
    st.error(
        "Your file is missing required columns for the report:\n\n- " +
        "\n- ".join(missing_for_report)
    )
    st.stop()

# Keep only columns we recognized, then rename to internal keys
df = df_raw[list(col_map.values())].copy()
df.columns = [k for k in col_map.keys()]

# Parse datetimes
for k in set(DATETIME_KEYS).intersection(df.columns):
    df[k] = to_datetime(df[k])

# Ensure arrival delta exists (minutes)
if "arrival_delta_min" not in df.columns:
    df["arrival_delta_min"] = df.apply(compute_arrival_delta_minutes, axis=1)

# ---------- Sidebar: Filters ----------
with st.sidebar:
    st.header("2) Filters")

    # Stop names - Exclude mode
    all_stops = sorted([s for s in df["stop_name"].dropna().astype(str).unique()])
    exclude_stops = st.multiselect(
        "Exclude these Stop names",
        options=all_stops,
        default=[],
        help="Start typing to find stops to exclude"
    )

    # Carriers - Exclude mode (as requested)
    all_carriers = sorted([c for c in df["current_carrier"].dropna().astype(str).unique()])
    exclude_carriers = st.multiselect(
        "Exclude these Carriers",
        options=all_carriers,
        default=[],
        help="Start typing to find carriers to exclude"
    )

    # Date range on Created time
    created_non_null = df["created_time"].dropna()
    if created_non_null.empty:
        st.warning("No valid 'Created time' values found. Date filter disabled.")
        start_date, end_date = None, None
    else:
        min_date = created_non_null.min().date()
        max_date = created_non_null.max().date()
        start_date, end_date = st.date_input(
            "Created time range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    st.header("3) On-time Rule")

    rule = st.radio(
        "Choose the on-time threshold",
        options=["≤ 0 min (exact on time or early)", "≤ 5 min", "≤ 10 min", "Custom…"],
        index=1
    )
    if rule == "≤ 0 min (exact on time or early)":
        threshold = 0
    elif rule == "≤ 5 min":
        threshold = 5
    elif rule == "≤ 10 min":
        threshold = 10
    else:
        threshold = st.number_input("Custom threshold (minutes, late allowed):", min_value=0, value=5, step=1)

    prefer_explicit_delta = st.checkbox(
        "Prefer 'Stop arrival delta (minutes)' over recomputing from timestamps",
        value=True
    )

# ---------- Apply filters ----------
mask = pd.Series(True, index=df.index)

if exclude_stops:
    mask &= ~df["stop_name"].astype(str).isin(set(exclude_stops))

if exclude_carriers:
    mask &= ~df["current_carrier"].astype(str).isin(set(exclude_carriers))

if start_date and end_date:
    # Include entire end day
    start_dt = pd.to_datetime(datetime.combine(start_date, datetime.min.time()))
    end_dt = pd.to_datetime(datetime.combine(end_date, datetime.max.time()))
    mask &= df["created_time"].between(start_dt, end_dt)

filtered = df[mask].copy()

# ---------- Compute on-time ----------
if prefer_explicit_delta or filtered["arrival_delta_min"].notna().any():
    delta = filtered["arrival_delta_min"]
else:
    # recompute from timestamps just in case (robustness)
    delta = filtered.apply(compute_arrival_delta_minutes, axis=1)

filtered["is_on_time"] = delta.apply(lambda x: apply_on_time_rule(x, threshold))

# ---------- Report ----------
st.subheader("Results")

left, mid, right = st.columns(3)
with left:
    st.metric("Stops (after filters)", f"{len(filtered):,}")
with mid:
    valid = filtered["is_on_time"].notna().sum()
    st.metric("Stops w/ valid arrival delta", f"{valid:,}")
with right:
    ontime = filtered["is_on_time"].sum(skipna=True)
    rate = (ontime / valid * 100) if valid else 0.0
    st.metric("On-time rate", f"{rate:.1f}%")

# Group by carrier
if "current_carrier" not in filtered.columns or filtered.empty:
    st.warning("No data available to aggregate by carrier with the current filters.")
else:
    grp = (
        filtered
        .groupby("current_carrier", dropna=False)
        .agg(
            total_stops=("is_on_time", "count"),
            on_time_stops=("is_on_time", lambda s: s.fillna(False).sum()),
        )
        .reset_index()
    )
    grp["on_time_rate"] = np.where(grp["total_stops"] > 0, grp["on_time_stops"] / grp["total_stops"], np.nan)

    st.markdown("### On-time by Carrier")
    st.dataframe(
        grp.sort_values(["on_time_rate", "total_stops"], ascending=[False, False])
          .assign(on_time_rate=lambda d: (d["on_time_rate"] * 100).round(1))
          .rename(columns={"current_carrier": "Carrier", "on_time_rate": "On-time %"})
    )

    # Chart
    if not grp.empty and grp["on_time_rate"].notna().any():
        chart_data = grp.copy()
        chart_data["On-time %"] = (chart_data["on_time_rate"] * 100).round(2)
        chart = (
            alt.Chart(chart_data)
            .mark_bar()
            .encode(
                x=alt.X("current_carrier:N", title="Carrier", sort="-y"),
                y=alt.Y("On-time %:Q", title="On-time (%)"),
                tooltip=[
                    alt.Tooltip("current_carrier:N", title="Carrier"),
                    alt.Tooltip("total_stops:Q", title="Total stops"),
                    alt.Tooltip("on_time_stops:Q", title="On-time stops"),
                    alt.Tooltip("On-time %:Q"),
                ]
            )
            .properties(height=420)
        )
        st.altair_chart(chart, use_container_width=True)

# ---------- Downloads ----------
st.subheader("Downloads")
col1, col2 = st.columns(2)

with col1:
    st.download_button(
        "Download filtered rows (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"filtered_stops_{date.today().isoformat()}.csv",
        mime="text/csv"
    )

with col2:
    out = grp.copy() if 'grp' in locals() else pd.DataFrame()
    csv = out.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download on-time by carrier (CSV)",
        data=csv,
        file_name=f"on_time_by_carrier_{date.today().isoformat()}.csv",
        mime="text/csv",
        disabled=out.empty
    )

# ---------- Details / Diagnostics ----------
with st.expander("Column Mapping & Data Health"):
    st.write("**Recognized columns** (Excel → internal):")
    mapped = {EXPECTED_COLUMNS[k]: col_map[k] for k in col_map}
    st.json(mapped)

    # Quick NA summary for key fields
    key_cols = ["stop_name", "current_carrier", "planned_arrival_start", "actual_arrival", "arrival_delta_min", "created_time"]
    present_keys = [c for c in key_cols if c in filtered.columns]
    if present_keys:
        st.write("**Nulls in key columns (after filters):**")
        st.write(filtered[present_keys].isna().sum())
