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
        a = row.get("actual_arrival")
        p = row.get("planned_arrival_start")
        if pd.notna(a) and pd.notna(p):
            return (a - p).total_seconds() / 60.0
    except Exception:
        pass
    return np.nan

def apply_on_time_rule(delta_minutes, threshold_minutes):
    # Robust: return NaN when the delta can't be parsed
    if pd.isna(delta_minutes):
        return np.nan
    try:
        return float(delta_minutes) <= float(threshold_minutes)
    except Exception:
        return np.nan

# ---------- Sidebar: File upload ----------
with st.sidebar:
    st.header("1) Upload Excel")
    uploaded = st.file_uploader("Choose an .xlsx file", type=["xlsx"])

    st.markdown(
        """
        **Notes**
        - All timestamps are treated as the **same timezone** (as per your data).
        - If **Stop arrival delta (minutes)** is missing or non-numeric, the app computes it from
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

# Build missing list using keys first, then convert to labels
missing_keys = [k for k in REQUIRED_FOR_REPORT if k not in col_map]
# 'arrival_delta_min' is preferred but we can compute if the timestamps are present
if "arrival_delta_min" in missing_keys and all(
    k in col_map for k in ["planned_arrival_start", "actual_arrival"]
):
    missing_keys.remove("arrival_delta_min")

missing_for_report = [EXPECTED_COLUMNS[k] for k in missing_keys]
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

# Trim whitespace & normalize empties in object columns
for c in df.columns:
    if df[c].dtype == "object":
        df[c] = df[c].astype(str).str.strip()
        df[c] = df[c].replace({"": np.nan})

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

    # Carriers - Exclude mode
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
# Build a numeric delta series (coerce strings like ' ' → NaN).
if prefer_explicit_delta and "arrival_delta_min" in filtered.columns:
    delta_series = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")
else:
    delta_series = filtered.apply(compute_arrival_delta_minutes, axis=1)

# If recomputed/all-NaN, try the other source as a fallback
if delta_series.notna().sum() == 0:
    if prefer_explicit_delta:
        # fallback to recompute
        delta_series = filtered.apply(compute_arrival_delta_minutes, axis=1)
    elif "arrival_delta_min" in filtered.columns:
        # fallback to explicit numeric
        delta_series = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")

filtered["is_on_time"] = delta_series.apply(lambda x: apply_on_time_rule(x, threshold))

# Flags for visibility and aggregation
filtered["valid_for_ontime"] = delta_series.notna()
filtered["no_arrival_time"] = filtered["actual_arrival"].isna()

# ---------- Report ----------
st.subheader("Results")

left, mid, right = st.columns(3)
with left:
    st.metric("Stops (after filters)", f"{len(filtered):,}")

with mid:
    valid = int(filtered["valid_for_ontime"].sum())
    st.metric("Stops with arrival data", f"{valid:,}")

with right:
    no_arrival_ct = int(filtered["no_arrival_time"].sum())
    st.metric("Stops with no arrival time", f"{no_arrival_ct:,}")

# On-time rate among stops with arrival data
ontime = int(filtered["is_on_time"].fillna(False).sum())
rate = (ontime / valid * 100) if valid else 0.0
st.metric("On-time rate (of those with arrival data)", f"{rate:.1f}%")

# Group by carrier
if "current_carrier" not in filtered.columns or filtered.empty:
    st.warning("No data available to aggregate by carrier with the current filters.")
else:
    grp = (
        filtered
        .groupby("current_carrier", dropna=False)
        .agg(
            total_stops=("stop_name", "size"),                 # includes rows with NA
            with_arrival_data=("valid_for_ontime", "sum"),     # rows where delta is evaluable
            on_time_stops=("is_on_time", lambda s: s.fillna(False).sum()),
            no_arrival_time=("no_arrival_time", "sum"),        # rows missing actual_arrival
        )
        .reset_index()
    )
    # On-time % computed only over those with arrival data
    grp["on_time_rate"] = np.where(grp["with_arrival_data"] > 0,
                                   grp["on_time_stops"] / grp["with_arrival_data"],
                                   np.nan)

    st.markdown("### On-time by Carrier")
    display_grp = (
        grp
        .assign(**{"On-time %": (grp["on_time_rate"] * 100).round(1)})
        .rename(columns={
            "current_carrier": "Carrier",
            "total_stops": "Total stops",
            "with_arrival_data": "With arrival data",
            "no_arrival_time": "No arrival time",
            "on_time_stops": "On-time stops",
        })[
            ["Carrier", "Total stops", "With arrival data", "No arrival time", "On-time stops", "On-time %"]
        ]
        .sort_values(["On-time %", "Total stops"], ascending=[False, False])
    )
    st.dataframe(display_grp, use_container_width=True)

    # Chart (On-time % by carrier)
    if grp["on_time_rate"].notna().any():
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
                    alt.Tooltip("with_arrival_data:Q", title="With arrival data"),
                    alt.Tooltip("no_arrival_time:Q", title="No arrival time"),
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
    if not out.empty:
        out = (
            out.assign(on_time_percent=(out["on_time_rate"] * 100).round(1))
               .rename(columns={
                    "current_carrier": "Carrier",
                    "total_stops": "Total stops",
                    "with_arrival_data": "With arrival data",
                    "no_arrival_time": "No arrival time",
                    "on_time_stops": "On-time stops",
                    "on_time_percent": "On-time %"
               })[
                    ["Carrier", "Total stops", "With arrival data", "No arrival time", "On-time stops", "On-time %"]
               ]
        )
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

    # Visibility on non-numeric deltas
    if "arrival_delta_min" in filtered.columns:
        tmp = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")
        st.write("Non-numeric 'Stop arrival delta (minutes)' after coercion:", int(tmp.isna().sum()))
