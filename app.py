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
st.caption("Upload your Excel → choose filters → see on-time performance by carrier and stop")

# ---------- Helpers ----------
EXPECTED_COLUMNS = {
    # left side = internal key ; right side = expected label (case/space tolerant)
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
    return {c: " ".join(str(c).strip().split()).lower() for c in cols}

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

# Missing required cols (keys → labels)
missing_keys = [k for k in REQUIRED_FOR_REPORT if k not in col_map]
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

# Keep only recognized columns; rename to internal keys
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

    avg_mode = st.radio(
        "Average delay mode",
        options=["Raw delay (late only)", "Overage beyond threshold (late only)"],
        index=0,
        help="Raw delay averages the minutes late. Overage averages how far past the threshold you were."
    )
    avg_overage = (avg_mode == "Overage beyond threshold (late only)")

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

# ---------- Compute deltas & flags ----------
# Primary delay series (minutes)
if prefer_explicit_delta and "arrival_delta_min" in filtered.columns:
    delta_series = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")
else:
    delta_series = filtered.apply(compute_arrival_delta_minutes, axis=1)

# Fallback if unusable
if delta_series.notna().sum() == 0:
    if prefer_explicit_delta:
        delta_series = filtered.apply(compute_arrival_delta_minutes, axis=1)
    elif "arrival_delta_min" in filtered.columns:
        delta_series = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")

filtered["delay_minutes"] = delta_series
filtered["is_on_time"] = filtered["delay_minutes"].apply(lambda x: apply_on_time_rule(x, threshold))
filtered["arrival_present"] = filtered["actual_arrival"].notna()          # data presence (reported arrival)
filtered["valid_for_ontime"] = filtered["delay_minutes"].notna()          # can evaluate on-time
filtered["is_late"] = filtered["valid_for_ontime"] & (filtered["delay_minutes"] > float(threshold))
filtered["no_arrival_time"] = ~filtered["arrival_present"]

# Late metric for averaging (dynamic: raw vs overage)
if avg_overage:
    filtered["late_metric"] = filtered["delay_minutes"].sub(float(threshold)).where(filtered["is_late"])
else:
    filtered["late_metric"] = filtered["delay_minutes"].where(filtered["is_late"])

# ---------- KPIs ----------
st.subheader("Results")

k1, k2, k3, k4, k5 = st.columns(5)
total_rows = len(filtered)
with_arrival = int(filtered["arrival_present"].sum())
reportable = int(filtered["valid_for_ontime"].sum())
no_arrival_ct = int(filtered["no_arrival_time"].sum())
late_ct = int(filtered["is_late"].fillna(False).sum())

data_presence_pct = (with_arrival / total_rows * 100) if total_rows else 0.0
late_pct_reported = (late_ct / reportable * 100) if reportable else 0.0
avg_late_val = float(filtered["late_metric"].mean()) if late_ct else 0.0
avg_label = "Avg overage (late, min)" if avg_overage else "Avg delay (late, min)"

with k1: st.metric("Stops (after filters)", f"{total_rows:,}")
with k2: st.metric("With arrival data", f"{with_arrival:,}", f"{data_presence_pct:.1f}% data presence")
with k3: st.metric("No arrival time", f"{no_arrival_ct:,}")
with k4: st.metric("Late % (of reported)", f"{late_pct_reported:.1f}%")
with k5: st.metric(avg_label, f"{avg_late_val:.1f} min")

# ---------- Tabs ----------
tab_carrier, tab_stop = st.tabs(["📦 Carrier summary", "📍 Stop-level analysis"])

# ===== Carrier Summary =====
with tab_carrier:
    if "current_carrier" not in filtered.columns or filtered.empty:
        st.warning("No data available to aggregate by carrier with the current filters.")
    else:
        grp = (
            filtered
            .groupby("current_carrier", dropna=False)
            .agg(
                total_stops=("stop_name", "size"),
                arrival_present=("arrival_present", "sum"),
                reportable=("valid_for_ontime", "sum"),
                on_time_stops=("is_on_time", lambda s: s.fillna(False).sum()),
                late_stops=("is_late", lambda s: s.fillna(False).sum()),
                no_arrival_time=("no_arrival_time", "sum"),
                avg_late_metric=("late_metric", "mean"),
            )
            .reset_index()
        )

        # Rates
        grp["data_presence_%"] = np.where(grp["total_stops"] > 0, grp["arrival_present"] / grp["total_stops"] * 100, np.nan)
        grp["on_time_%"] = np.where(grp["reportable"] > 0, grp["on_time_stops"] / grp["reportable"] * 100, np.nan)
        grp["late_%"] = np.where(grp["reportable"] > 0, grp["late_stops"] / grp["reportable"] * 100, np.nan)

        # Display table
        display_grp = (
            grp.rename(columns={"current_carrier": "Carrier"})
               .assign(
                    **{
                        "Data presence %": grp["data_presence_%"].round(1),
                        "On-time % (reported)": grp["on_time_%"].round(1),
                        "Late % (reported)": grp["late_%"].round(1),
                        avg_label: grp["avg_late_metric"].round(1),
                    }
                )[
                    [
                        "Carrier", "total_stops", "arrival_present", "reportable",
                        "on_time_stops", "late_stops", "no_arrival_time",
                        "Data presence %", "On-time % (reported)", "Late % (reported)", avg_label
                    ]
                ]
                .rename(columns={
                    "total_stops": "Total stops",
                    "arrival_present": "With arrival data",
                    "reportable": "Reported (evaluable)",
                    "on_time_stops": "On-time stops",
                    "late_stops": "Late stops",
                    "no_arrival_time": "No arrival time",
                })
                .sort_values(["Late % (reported)", "Total stops"], ascending=[False, False])
        )

        st.markdown("### On-time / Late by Carrier")
        st.dataframe(display_grp, use_container_width=True)

        # Chart: On-time % by carrier
        if grp["on_time_%"].notna().any():
            chart_data = grp.copy()
            chart_data["On-time %"] = chart_data["on_time_%"].round(2)
            chart = (
                alt.Chart(chart_data)
                .mark_bar()
                .encode(
                    x=alt.X("current_carrier:N", title="Carrier", sort="-y"),
                    y=alt.Y("On-time %:Q", title="On-time (%)"),
                    tooltip=[
                        alt.Tooltip("current_carrier:N", title="Carrier"),
                        alt.Tooltip("total_stops:Q", title="Total stops"),
                        alt.Tooltip("arrival_present:Q", title="With arrival data"),
                        alt.Tooltip("reportable:Q", title="Reported (evaluable)"),
                        alt.Tooltip("on_time_stops:Q", title="On-time stops"),
                        alt.Tooltip("late_stops:Q", title="Late stops"),
                        alt.Tooltip("no_arrival_time:Q", title="No arrival time"),
                        alt.Tooltip("On-time %:Q"),
                    ]
                )
                .properties(height=420)
            )
            st.altair_chart(chart, use_container_width=True)

        # Download
        csv = display_grp.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download carrier summary (CSV)",
            data=csv,
            file_name=f"carrier_summary_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

# ===== Stop-level Analysis =====
with tab_stop:
    st.markdown("### Stop-level performance (overall and by carrier)")

    # Overall by stop (all carriers combined)
    stop_overall = (
        filtered
        .groupby("stop_name", dropna=False)
        .agg(
            total_stops=("stop_name", "size"),
            arrival_present=("arrival_present", "sum"),
            reportable=("valid_for_ontime", "sum"),
            on_time_stops=("is_on_time", lambda s: s.fillna(False).sum()),
            late_stops=("is_late", lambda s: s.fillna(False).sum()),
            no_arrival_time=("no_arrival_time", "sum"),
            avg_late_metric=("late_metric", "mean"),
        )
        .reset_index()
    )
    stop_overall["data_presence_%"] = np.where(stop_overall["total_stops"] > 0,
                                               stop_overall["arrival_present"] / stop_overall["total_stops"] * 100, np.nan)
    stop_overall["on_time_%"] = np.where(stop_overall["reportable"] > 0,
                                         stop_overall["on_time_stops"] / stop_overall["reportable"] * 100, np.nan)
    stop_overall["late_%"] = np.where(stop_overall["reportable"] > 0,
                                      stop_overall["late_stops"] / stop_overall["reportable"] * 100, np.nan)

    # By stop + carrier
    stop_by_carrier = (
        filtered
        .groupby(["stop_name", "current_carrier"], dropna=False)
        .agg(
            total_stops=("stop_name", "size"),
            arrival_present=("arrival_present", "sum"),
            reportable=("valid_for_ontime", "sum"),
            on_time_stops=("is_on_time", lambda s: s.fillna(False).sum()),
            late_stops=("is_late", lambda s: s.fillna(False).sum()),
            no_arrival_time=("no_arrival_time", "sum"),
            avg_late_metric=("late_metric", "mean"),
        )
        .reset_index()
        .rename(columns={"current_carrier": "Carrier"})
    )
    stop_by_carrier["data_presence_%"] = np.where(stop_by_carrier["total_stops"] > 0,
                                                  stop_by_carrier["arrival_present"] / stop_by_carrier["total_stops"] * 100, np.nan)
    stop_by_carrier["on_time_%"] = np.where(stop_by_carrier["reportable"] > 0,
                                            stop_by_carrier["on_time_stops"] / stop_by_carrier["reportable"] * 100, np.nan)
    stop_by_carrier["late_%"] = np.where(stop_by_carrier["reportable"] > 0,
                                         stop_by_carrier["late_stops"] / stop_by_carrier["reportable"] * 100, np.nan)

    # Controls
    all_stop_names = sorted([s for s in stop_overall["stop_name"].astype(str).unique()])
    default_top = min(25, len(all_stop_names))
    col_sel1, col_sel2 = st.columns([2,1])
    with col_sel1:
        focus_stops = st.multiselect("Focus on specific Stop names (optional)", options=all_stop_names, default=[])
    with col_sel2:
        top_n = st.number_input("Show top N by total stops (if no selection)", min_value=1, max_value=max(1, len(all_stop_names)), value=default_top, step=1)

    # Filter tables based on selection
    if focus_stops:
        so = stop_overall[stop_overall["stop_name"].astype(str).isin(set(focus_stops))].copy()
        sbc = stop_by_carrier[stop_by_carrier["stop_name"].astype(str).isin(set(focus_stops))].copy()
    else:
        so = stop_overall.sort_values("total_stops", ascending=False).head(top_n).copy()
        sbc = stop_by_carrier[stop_by_carrier["stop_name"].isin(so["stop_name"])].copy()

    # Display: overall by stop
    so_disp = (
        so.assign(
            **{
                "Data presence %": so["data_presence_%"].round(1),
                "On-time % (reported)": so["on_time_%"].round(1),
                "Late % (reported)": so["late_%"].round(1),
                avg_label: so["avg_late_metric"].round(1),
            }
        )[
            [
                "stop_name", "total_stops", "arrival_present", "reportable",
                "on_time_stops", "late_stops", "no_arrival_time",
                "Data presence %", "On-time % (reported)", "Late % (reported)", avg_label
            ]
        ]
        .rename(columns={
            "stop_name": "Stop",
            "total_stops": "Total stops",
            "arrival_present": "With arrival data",
            "reportable": "Reported (evaluable)",
            "on_time_stops": "On-time stops",
            "late_stops": "Late stops",
            "no_arrival_time": "No arrival time",
        })
    )
    st.markdown("#### Overall by Stop")
    st.dataframe(so_disp, use_container_width=True)

    # Display: by stop + carrier (who served on time / late / not reported)
    sbc_disp = (
        sbc.assign(
            **{
                "Data presence %": sbc["data_presence_%"].round(1),
                "On-time % (reported)": sbc["on_time_%"].round(1),
                "Late % (reported)": sbc["late_%"].round(1),
                avg_label: sbc["avg_late_metric"].round(1),
            }
        )[
            [
                "stop_name", "Carrier", "total_stops", "arrival_present", "reportable",
                "on_time_stops", "late_stops", "no_arrival_time",
                "Data presence %", "On-time % (reported)", "Late % (reported)", avg_label
            ]
        ]
        .rename(columns={
            "stop_name": "Stop",
            "total_stops": "Total stops",
            "arrival_present": "With arrival data",
            "reportable": "Reported (evaluable)",
            "on_time_stops": "On-time stops",
            "late_stops": "Late stops",
            "no_arrival_time": "No arrival time",
        })
        .sort_values(["Stop", "Late % (reported)", "Total stops"], ascending=[True, False, False])
    )
    st.markdown("#### By Stop × Carrier (who served on time / late / not reported)")
    st.dataframe(sbc_disp, use_container_width=True)

    # Downloads
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Download stop overall (CSV)",
            data=so_disp.to_csv(index=False).encode("utf-8"),
            file_name=f"stop_overall_{date.today().isoformat()}.csv",
            mime="text/csv",
        )
    with c2:
        st.download_button(
            "Download stop × carrier (CSV)",
            data=sbc_disp.to_csv(index=False).encode("utf-8"),
            file_name=f"stop_by_carrier_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

# ---------- Downloads: filtered rows ----------
st.subheader("Filtered rows download")
st.download_button(
    "Download filtered rows (CSV)",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name=f"filtered_stops_{date.today().isoformat()}.csv",
    mime="text/csv"
)

# ---------- Details / Diagnostics ----------
with st.expander("Column Mapping & Data Health"):
    st.write("**Recognized columns** (Excel → internal):")
    mapped = {EXPECTED_COLUMNS[k]: col_map[k] for k in col_map}
    st.json(mapped)

    key_cols = ["stop_name", "current_carrier", "planned_arrival_start", "actual_arrival", "arrival_delta_min", "created_time"]
    present_keys = [c for c in key_cols if c in filtered.columns]
    if present_keys:
        st.write("**Nulls in key columns (after filters):**")
        st.write(filtered[present_keys].isna().sum())

    if "arrival_delta_min" in filtered.columns:
        tmp = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")
        st.write("Non-numeric 'Stop arrival delta (minutes)' after coercion:", int(tmp.isna().sum()))
