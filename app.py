import io
import json
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

# =====================================================================
#                           Page Setup
# =====================================================================
st.set_page_config(
    page_title="On-Time Arrival Report",
    page_icon="✅",
    layout="wide"
)

st.title("On-Time Arrival Report")
st.caption("Upload your Excel → choose filters → see on-time performance by carrier, stop, and shipment coverage")

# =====================================================================
#                        UI Beauty Pack ✨
# =====================================================================
def _register_altair_theme():
    def streamlit_nice():
        return {
            "config": {
                "view": {"strokeWidth": 0},
                "axis": {
                    "grid": True,
                    "gridColor": "#eceff4",
                    "domainColor": "#d8dee9",
                    "labelColor": "#2e3440",
                    "titleColor": "#2e3440",
                    "labelFontSize": 12,
                    "titleFontSize": 13,
                },
                "legend": {"labelColor": "#2e3440", "titleColor": "#2e3440"},
                "range": {
                    "category": [
                        "#4e79a7","#f28e2b","#e15759","#76b7b2",
                        "#59a14f","#edc949","#af7aa1","#ff9da7",
                        "#9c755f","#bab0ab"
                    ]
                },
                "line": {"strokeWidth": 3},
                "bar": {"cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
                "area": {"opacity": 0.85}
            }
        }
    alt.themes.register("streamlit_nice", streamlit_nice)
    alt.themes.enable("streamlit_nice")

def polish_chart(c: alt.Chart, height=360):
    return (
        c.properties(height=height)
         .interactive()
         .configure_point(size=60)
         .configure_mark(tooltip=True)
    )

def inject_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 3rem; }
        h1, h2, h3 { letter-spacing: .2px; }
        button[role="tab"] { padding: .6rem 1rem !important; border-radius: 10px !important; }
        div[data-testid="stMetric"] {
            background: #f7f9fc; border: 1px solid #eef2f7;
            border-radius: 14px; padding: 12px 10px; box-shadow: 0 1px 2px rgba(0,0,0,.04);
        }
        div[data-testid="stDataFrame"] table { font-size: 0.92rem; }
        summary { font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )

from pandas.api.types import (
    is_datetime64_any_dtype as is_dt,
    is_integer_dtype,
    is_float_dtype,
)

def _guess_progress(col_name: str) -> bool:
    n = str(col_name).lower()
    return (
        "%" in n or "percent" in n or n.endswith(" pct") or n.endswith(" %")
        or "on-time" in n or "late %"
    )

def _guess_minutes(col_name: str) -> bool:
    n = str(col_name).lower()
    return "min" in n or "minute" in n or "(min" in n or n.endswith(" min")

def _mk_column_config(df: pd.DataFrame) -> dict:
    cfg = {}
    for c in df.columns:
        # datetime columns
        try:
            if is_dt(df[c]):
                cfg[c] = st.column_config.DatetimeColumn(c, format="YYYY-MM-DD HH:mm")
                continue
        except Exception:
            pass
        # percentages -> progress bars (0-100)
        if _guess_progress(c):
            cfg[c] = st.column_config.ProgressColumn(
                str(c), help="Percentage", format="%.1f%%", min_value=0, max_value=100
            )
            continue
        # minutes -> number with unit
        if _guess_minutes(c):
            cfg[c] = st.column_config.NumberColumn(str(c), format="%.1f min")
            continue
        # counts / integers
        try:
            if is_integer_dtype(df[c]):
                cfg[c] = st.column_config.NumberColumn(str(c), format="%d")
                continue
        except Exception:
            pass
        # floats (one decimal)
        try:
            if is_float_dtype(df[c]):
                cfg[c] = st.column_config.NumberColumn(str(c), format="%.1f")
                continue
        except Exception:
            pass
    return cfg

def pretty_df(df: pd.DataFrame, *, use_container_width=True, height=None, hide_index=True):
    """
    Drop-in replacement for st.dataframe with better formatting.
    Streamlit 1.36+: avoid passing height=None; only pass height if it's a positive int or "auto".
    """
    if df is None or df.empty:
        st.info("No data to display.")
        return

    cfg = _mk_column_config(df)

    kwargs = dict(
        use_container_width=use_container_width,
        hide_index=hide_index,
        column_config=cfg,
    )
    if isinstance(height, (int, np.integer)) and int(height) > 0:
        kwargs["height"] = int(height)
    elif height == "auto":
        kwargs["height"] = "auto"

    st.dataframe(df, **kwargs)

# Enable theme + CSS
_register_altair_theme()
inject_css()

# =====================================================================
#                              Helpers
# =====================================================================
EXPECTED_COLUMNS = {
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
    "planned_arrival_end",
    "actual_arrival",
    "arrival_delta_min",  # preferred, but we will compute if missing
    "current_carrier",
    "created_time",
    "shipment_id",
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
    try:
        a = row.get("actual_arrival")
        p = row.get("planned_arrival_start")
        if pd.notna(a) and pd.notna(p):
            return (a - p).total_seconds() / 60.0
    except Exception:
        pass
    return np.nan

def apply_on_time_rule(delta_minutes, threshold_minutes):
    if pd.isna(delta_minutes):
        return np.nan
    try:
        return float(delta_minutes) <= float(threshold_minutes)
    except Exception:
        return np.nan

def safe_mode(series: pd.Series, fallback="(Unknown)"):
    ser = series.dropna().astype(str)
    if ser.empty:
        return fallback
    vc = ser.value_counts()
    return vc.index[0] if not vc.empty else fallback

# =====================================================================
#                           Sidebar: File upload
# =====================================================================
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

# =====================================================================
#                         Load & validate
# =====================================================================
try:
    df_raw = read_excel(uploaded)
except Exception as e:
    st.error(f"Could not read Excel: {e}")
    st.stop()

if df_raw.empty:
    st.warning("The uploaded Excel appears to be empty.")
    st.stop()

col_map = build_column_map(df_raw.columns)

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

# =====================================================================
#                            Sidebar: Filters
# =====================================================================
with st.sidebar:
    st.header("2) Filters")

    filter_mode = st.radio(
        "Filter mode",
        options=["Exclude", "Include"],
        index=0,
        key="filter_mode",
        help="Exclude: remove selected. Include: keep only selected (if none selected, keep all)."
    )

    all_stops = sorted([s for s in df["stop_name"].dropna().astype(str).unique()])
    stop_selection = st.multiselect(
        "Stop names",
        options=all_stops,
        default=[],
        key="stops_select",
        help="Select stops to Exclude/Include per the filter mode above."
    )

    all_carriers = sorted([c for c in df["current_carrier"].dropna().astype(str).unique()])
    carrier_selection = st.multiselect(
        "Carriers",
        options=all_carriers,
        default=[],
        key="carriers_select",
        help="Select carriers to Exclude/Include per the filter mode above."
    )

    created_non_null = df["created_time"].dropna()
    if created_non_null.empty:
        st.warning("No valid 'Created time' values found. Date filter disabled.")
        start_date, end_date = None, None
        default_range = None
    else:
        min_date = created_non_null.min().date()
        max_date = created_non_null.max().date()
        start_date, end_date = st.date_input(
            "Created time range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="created_range"
        )
        default_range = (min_date, max_date)

    st.header("3) On-time Rule")

    rule = st.radio(
        "Choose the on-time threshold",
        options=["≤ 0 min (exact on time or early)", "≤ 5 min", "≤ 10 min", "Custom…"],
        index=1,
        key="ontime_rule"
    )
    if rule == "≤ 0 min (exact on time or early)":
        threshold = 0
    elif rule == "≤ 5 min":
        threshold = 5
    elif rule == "≤ 10 min":
        threshold = 10
    else:
        threshold = st.number_input("Custom threshold (minutes, late allowed):", min_value=0, value=5, step=1, key="custom_thresh")

    prefer_explicit_delta = st.checkbox(
        "Prefer 'Stop arrival delta (minutes)' over recomputing from timestamps (planned-start based)",
        value=True,
        key="prefer_explicit"
    )

    avg_mode = st.radio(
        "Average delay mode",
        options=["Raw delay (late only)", "Overage beyond threshold (late only)"],
        index=0,
        key="avg_mode",
        help="Raw delay averages the minutes late. Overage averages how far past the threshold you were."
    )
    avg_overage_sidebar = (avg_mode == "Overage beyond threshold (late only)")

    st.header("4) SLA Bands (based on overage beyond threshold)")
    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1: sla_b1 = st.number_input("Band 1 (min)", min_value=1, value=5, step=1, key="sla_b1")
    with c_b2: sla_b2 = st.number_input("Band 2 (min)", min_value=sla_b1+1, value=15, step=1, key="sla_b2")
    with c_b3: sla_b3 = st.number_input("Band 3 (min)", min_value=sla_b2+1, value=30, step=1, key="sla_b3")

    with st.expander("💾 Presets (save / load)"):
        cr_state = st.session_state.get("created_range", default_range)
        if cr_state:
            cr_serialized = [cr_state[0].isoformat(), cr_state[1].isoformat()]
        else:
            cr_serialized = [None, None]

        preset_dict = {
            "filter_mode": st.session_state.get("filter_mode"),
            "stops": st.session_state.get("stops_select", []),
            "carriers": st.session_state.get("carriers_select", []),
            "created_range": cr_serialized,
            "threshold": int(threshold),
            "prefer_explicit": st.session_state.get("prefer_explicit", True),
            "avg_mode": st.session_state.get("avg_mode"),
            "sla_b1": int(sla_b1),
            "sla_b2": int(sla_b2),
            "sla_b3": int(sla_b3),
        }
        st.download_button(
            "Download current preset (JSON)",
            data=json.dumps(preset_dict, indent=2).encode("utf-8"),
            file_name="ontime_preset.json",
            mime="application/json",
        )

        up = st.file_uploader("Load preset (JSON)", type=["json"], key="preset_file")
        if up is not None and st.button("Apply preset"):
            try:
                preset = json.load(up)
                st.session_state["filter_mode"] = preset.get("filter_mode", "Exclude")
                st.session_state["stops_select"] = preset.get("stops", [])
                st.session_state["carriers_select"] = preset.get("carriers", [])
                cr = preset.get("created_range", [])
                if cr and len(cr) == 2 and cr[0] and cr[1]:
                    st.session_state["created_range"] = (date.fromisoformat(cr[0]), date.fromisoformat(cr[1]))
                st.session_state["ontime_rule"] = "Custom…"
                st.session_state["custom_thresh"] = int(preset.get("threshold", 5))
                st.session_state["prefer_explicit"] = bool(preset.get("prefer_explicit", True))
                st.session_state["avg_mode"] = preset.get("avg_mode", "Raw delay (late only)")
                st.session_state["sla_b1"] = int(preset.get("sla_b1", 5))
                st.session_state["sla_b2"] = int(preset.get("sla_b2", 15))
                st.session_state["sla_b3"] = int(preset.get("sla_b3", 30))
                st.rerun()
            except Exception as e:
                st.error(f"Could not apply preset: {e}")

# =====================================================================
#                           Apply filters
# =====================================================================
mask = pd.Series(True, index=df.index)

# Stop names
if filter_mode == "Exclude":
    if stop_selection:
        mask &= ~df["stop_name"].astype(str).isin(set(stop_selection))
else:  # Include
    if stop_selection:
        mask &= df["stop_name"].astype(str).isin(set(stop_selection))

# Carriers
if filter_mode == "Exclude":
    if carrier_selection:
        mask &= ~df["current_carrier"].astype(str).isin(set(carrier_selection))
else:
    if carrier_selection:
        mask &= df["current_carrier"].astype(str).isin(set(carrier_selection))

# Date range
if isinstance(start_date, date) and isinstance(end_date, date):
    start_dt = pd.to_datetime(datetime.combine(start_date, datetime.min.time()))
    end_dt = pd.to_datetime(datetime.combine(end_date, datetime.max.time()))
    mask &= df["created_time"].between(start_dt, end_dt)

filtered = df[mask].copy()

# =====================================================================
#             Compute deltas & flags (planned-start basis)
# =====================================================================
if "arrival_delta_min" in filtered.columns and st.session_state.get("prefer_explicit", True):
    delta_series = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")
else:
    delta_series = filtered.apply(compute_arrival_delta_minutes, axis=1)

if delta_series.notna().sum() == 0:
    if st.session_state.get("prefer_explicit", True):
        delta_series = filtered.apply(compute_arrival_delta_minutes, axis=1)
    elif "arrival_delta_min" in filtered.columns:
        delta_series = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")

filtered["delay_minutes"] = delta_series
filtered["is_on_time"] = filtered["delay_minutes"].apply(lambda x: apply_on_time_rule(x, threshold))
filtered["arrival_present"] = filtered["actual_arrival"].notna()
filtered["valid_for_ontime"] = filtered["delay_minutes"].notna()
filtered["is_late"] = filtered["valid_for_ontime"] & (filtered["delay_minutes"] > float(threshold))
filtered["no_arrival_time"] = ~filtered["arrival_present"]

# Late metric for averaging (dynamic: raw vs overage)
avg_overage = (st.session_state.get("avg_mode") == "Overage beyond threshold (late only)")
if avg_overage:
    filtered["late_metric"] = filtered["delay_minutes"].sub(float(threshold)).where(filtered["is_late"])
else:
    filtered["late_metric"] = filtered["delay_minutes"].where(filtered["is_late"])

# SLA bands (use overage)
sla_b1 = st.session_state.get("sla_b1", 5)
sla_b2 = st.session_state.get("sla_b2", 15)
sla_b3 = st.session_state.get("sla_b3", 30)

filtered["overage_minutes"] = filtered["delay_minutes"].sub(float(threshold)).clip(lower=0)
def _sla_band(row):
    if row["no_arrival_time"]:
        return "No arrival"
    v = row["overage_minutes"]
    if pd.isna(v):
        return "Not evaluable"
    if v == 0:
        return "On-time/early"
    if v <= sla_b1:
        return f"≤{sla_b1} min late"
    if v <= sla_b2:
        return f"{sla_b1+1}–{sla_b2} min late"
    if v <= sla_b3:
        return f"{sla_b2+1}–{sla_b3} min late"
    return f">{sla_b3} min late"

filtered["sla_band"] = filtered.apply(_sla_band, axis=1)

# =====================================================================
#                               KPIs
# =====================================================================
st.subheader("Results ✨")

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

# =====================================================================
#                                 Tabs
# =====================================================================
tab_carrier, tab_stop, tab_trend, tab_ship = st.tabs([
    "📦 Carrier summary",
    "📍 Stop-level analysis",
    "📈 Trends",
    "🚚 Shipment coverage",
])

display_grp = pd.DataFrame()
so_disp = pd.DataFrame()
sbc_disp = pd.DataFrame()
trend_disp = pd.DataFrame()
ship_carrier_disp = pd.DataFrame()
ship_detail_disp = pd.DataFrame()

# =========================== Carrier Summary ==========================
with tab_carrier:
    st.markdown("### On-time / Late by Carrier 🚚")
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

        grp["data_presence_%"] = np.where(grp["total_stops"] > 0, grp["arrival_present"] / grp["total_stops"] * 100, np.nan)
        grp["on_time_%"] = np.where(grp["reportable"] > 0, grp["on_time_stops"] / grp["reportable"] * 100, np.nan)
        grp["late_%"] = np.where(grp["reportable"] > 0, grp["late_stops"] / grp["reportable"] * 100, np.nan)

        sla_counts = filtered.groupby(["current_carrier", "sla_band"]).size().reset_index(name="count")
        total_by_carrier = sla_counts.groupby("current_carrier")["count"].transform("sum")
        sla_counts["percent"] = np.where(total_by_carrier > 0, sla_counts["count"] / total_by_carrier * 100, np.nan)

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

        pretty_df(display_grp, use_container_width=True)

        st.markdown("#### SLA distribution by Carrier 📊")
        if not sla_counts.empty:
            chart = (
                alt.Chart(sla_counts)
                .mark_bar()
                .encode(
                    x=alt.X("current_carrier:N", title="Carrier"),
                    y=alt.Y("percent:Q", stack="normalize", title="Share of stops (%)"),
                    color=alt.Color("sla_band:N", title="SLA band"),
                    tooltip=[
                        alt.Tooltip("current_carrier:N", title="Carrier"),
                        alt.Tooltip("sla_band:N", title="Band"),
                        alt.Tooltip("count:Q", title="Stops"),
                        alt.Tooltip("percent:Q", title="%"),
                    ]
                )
            )
            st.altair_chart(polish_chart(chart, height=420), use_container_width=True)
        else:
            st.info("No SLA distribution to display.")

        csv = display_grp.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download carrier summary (CSV)",
            data=csv,
            file_name=f"carrier_summary_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

# ========================= Stop-level Analysis ========================
with tab_stop:
    st.markdown("### Stop-level performance (overall and by carrier) 🧭")

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

    st.markdown("##### SLA distribution (select a stop to focus)")
    chosen_stop = st.selectbox("Pick a stop (optional)", options=["(All)"] + sorted([str(s) for s in filtered["stop_name"].dropna().unique()]))
    if chosen_stop and chosen_stop != "(All)":
        sla_by = filtered[filtered["stop_name"].astype(str) == chosen_stop]
    else:
        sla_by = filtered
    sla_counts_stop = sla_by.groupby(["stop_name", "sla_band"]).size().reset_index(name="count")
    total_by_stop = sla_counts_stop.groupby("stop_name")["count"].transform("sum")
    sla_counts_stop["percent"] = np.where(total_by_stop > 0, sla_counts_stop["count"] / total_by_stop * 100, np.nan)

    if not sla_counts_stop.empty:
        chart2 = (
            alt.Chart(sla_counts_stop)
            .mark_bar()
            .encode(
                x=alt.X("sla_band:N", title="SLA band"),
                y=alt.Y("percent:Q", title="Share of stops (%)"),
                column=alt.Column("stop_name:N", title="Stop", header=alt.Header(labelOrient="bottom")),
                tooltip=[alt.Tooltip("stop_name:N", title="Stop"),
                         alt.Tooltip("sla_band:N", title="Band"),
                         alt.Tooltip("count:Q", title="Stops"),
                         alt.Tooltip("percent:Q", title="%")],
            )
        )
        st.altair_chart(polish_chart(chart2, height=360), use_container_width=True)

    all_stop_names = sorted([s for s in stop_overall["stop_name"].astype(str).unique()])
    default_top = min(25, len(all_stop_names))
    col_sel1, col_sel2 = st.columns([2,1])
    with col_sel1:
        focus_stops = st.multiselect("Focus on specific Stop names (optional)", options=all_stop_names, default=[])
    with col_sel2:
        top_n = st.number_input("Show top N by total stops (if no selection)", min_value=1, max_value=max(1, len(all_stop_names)), value=default_top, step=1)

    if focus_stops:
        so = stop_overall[stop_overall["stop_name"].astype(str).isin(set(focus_stops))].copy()
        sbc = stop_by_carrier[stop_by_carrier["stop_name"].astype(str).isin(set(focus_stops))].copy()
    else:
        so = stop_overall.sort_values("total_stops", ascending=False).head(top_n).copy()
        sbc = stop_by_carrier[stop_by_carrier["stop_name"].isin(so["stop_name"])].copy()

    st.markdown("#### Overall by Stop")
    so_disp = (
        so.assign(
            **{
                "Data presence %": so["data_presence_%"].round(1),
                "On-time % (reported)": so["on_time_%"].round(1),
                "Late % (reported)": so["late_%"].round(1),
                "Avg metric (late, min)": so["avg_late_metric"].round(1),
            }
        )[
            [
                "stop_name", "total_stops", "arrival_present", "reportable",
                "on_time_stops", "late_stops", "no_arrival_time",
                "Data presence %", "On-time % (reported)", "Late % (reported)", "Avg metric (late, min)"
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
    pretty_df(so_disp, use_container_width=True)

    st.markdown("#### By Stop × Carrier (who served on time / late / not reported)")
    sbc_disp = (
        sbc.assign(
            **{
                "Data presence %": sbc["data_presence_%"].round(1),
                "On-time % (reported)": sbc["on_time_%"].round(1),
                "Late % (reported)": sbc["late_%"].round(1),
                "Avg metric (late, min)": sbc["avg_late_metric"].round(1),
            }
        )[
            [
                "stop_name", "Carrier", "total_stops", "arrival_present", "reportable",
                "on_time_stops", "late_stops", "no_arrival_time",
                "Data presence %", "On-time % (reported)", "Late % (reported)", "Avg metric (late, min)"
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
    pretty_df(sbc_disp, use_container_width=True)

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

# =============================== Trends ===============================
with tab_trend:
    st.markdown("### On-time trends 📈")
    gran = st.radio("Granularity", options=["Daily", "Weekly"], index=0, horizontal=True)
    if gran == "Daily":
        grp = (
            filtered
            .assign(created_date=filtered["created_time"].dt.date)
            .groupby("created_date", dropna=False)
            .agg(
                total=("stop_name", "size"),
                reportable=("valid_for_ontime", "sum"),
                on_time=("is_on_time", lambda s: s.fillna(False).sum()),
                late=("is_late", lambda s: s.fillna(False).sum()),
                avg_metric=("late_metric", "mean"),
            )
            .reset_index()
            .rename(columns={"created_date": "date"})
            .sort_values("date")
        )
    else:
        grp = (
            filtered
            .groupby(pd.Grouper(key="created_time", freq="W-MON"))
            .agg(
                total=("stop_name", "size"),
                reportable=("valid_for_ontime", "sum"),
                on_time=("is_on_time", lambda s: s.fillna(False).sum()),
                late=("is_late", lambda s: s.fillna(False).sum()),
                avg_metric=("late_metric", "mean"),
            )
            .reset_index()
            .rename(columns={"created_time": "date"})
            .sort_values("date")
        )

    if grp.empty:
        st.info("No data for the selected period.")
    else:
        grp["on_time_%"] = np.where(grp["reportable"] > 0, grp["on_time"] / grp["reportable"] * 100, np.nan)

        trend_disp = grp.copy()
        pretty_df(trend_disp, use_container_width=True)

        line = (
            alt.Chart(grp)
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("on_time_%:Q", title="On-time (%)"),
                tooltip=[alt.Tooltip("date:T", title="Date"),
                         alt.Tooltip("on_time_%:Q", title="On-time %"),
                         alt.Tooltip("total:Q", title="Total"),
                         alt.Tooltip("reportable:Q", title="Reported"),
                         alt.Tooltip("avg_metric:Q", title="Avg late metric")]
            )
        )
        bars = (
            alt.Chart(grp)
            .mark_bar(opacity=0.4)
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("total:Q", title="Stops (total)"),
                tooltip=[alt.Tooltip("total:Q", title="Total")]
            )
        )
        st.altair_chart(polish_chart(bars, height=120), use_container_width=True)
        st.altair_chart(polish_chart(line, height=360), use_container_width=True)

        st.download_button(
            "Download trends (CSV)",
            data=trend_disp.to_csv(index=False).encode("utf-8"),
            file_name=f"trends_{gran.lower()}_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

# =========================== Shipment coverage ========================
with tab_ship:
    st.markdown("### Shipment coverage by Carrier (arrival vs *planned end* & event reporting) 🚚")
    # Arrival vs planned END
    filtered["delay_end_minutes"] = (
        (filtered["actual_arrival"] - filtered["planned_arrival_end"])
        .dt.total_seconds() / 60.0
    )
    filtered["on_time_end"] = filtered["delay_end_minutes"].apply(lambda x: apply_on_time_rule(x, threshold))

    # Role classification (origin/destination/other)
    filtered["role"] = "other"
    if "stop_type" in filtered.columns:
        stype = filtered["stop_type"].astype(str).str.lower()
        mask_origin = stype.str.contains("origin|pickup|source|load", na=False)
        mask_dest = stype.str.contains("destination|dest|drop|unload|delivery", na=False)
        filtered.loc[mask_origin, "role"] = "origin"
        filtered.loc[mask_dest, "role"] = "destination"
    if "origin" in filtered.columns:
        eq_origin = (filtered["stop_name"].astype(str).str.casefold() ==
                    filtered["origin"].astype(str).str.casefold())
        filtered.loc[eq_origin, "role"] = "origin"
    if "destination" in filtered.columns:
        eq_dest = (filtered["stop_name"].astype(str).str.casefold() ==
                  filtered["destination"].astype(str).str.casefold())
        filtered.loc[eq_dest, "role"] = "destination"

    def _infer_roles(g: pd.DataFrame):
        roles = g["role"].copy()
        if (roles == "origin").sum() == 0:
            t = g["planned_arrival_end"].copy()
            if t.isna().all():
                t = g["planned_arrival_start"].copy()
                if t.isna().all():
                    t = g["actual_arrival"].copy()
            if not t.isna().all():
                idx = t.idxmin()
                roles.loc[idx] = "origin"
        if (roles == "destination").sum() == 0:
            t = g["planned_arrival_end"].copy()
            if t.isna().all():
                t = g["planned_arrival_start"].copy()
                if t.isna().all():
                    t = g["actual_arrival"].copy()
            if not t.isna().all():
                idx = t.idxmax()
                roles.loc[idx] = "destination"
        return roles

    filtered["role"] = filtered.groupby("shipment_id", group_keys=False).apply(_infer_roles)

    # Per-shipment summary
    ship_rows = []
    for sid, g in filtered.groupby("shipment_id", dropna=False):
        g = g.copy()
        ship_carrier = safe_mode(g["current_carrier"], "(Unknown)")

        g_origin = g[g["role"] == "origin"]
        if not g_origin.empty:
            org_row = g_origin.sort_values("planned_arrival_end", na_position="last").iloc[0]
            origin_reported = pd.notna(org_row["actual_arrival"])
            origin_ontime = (org_row["delay_end_minutes"] <= float(threshold)) if origin_reported else np.nan
        else:
            origin_reported = False
            origin_ontime = np.nan

        g_other = g[g["role"] == "other"]
        if not g_other.empty:
            other_total = len(g_other)
            other_reported_ct = g_other["actual_arrival"].notna().sum()
            other_reported_pct = other_reported_ct / other_total if other_total > 0 else np.nan
            g_other_rep = g_other[g_other["actual_arrival"].notna()]
            other_ontime_pct = (
                (g_other_rep["delay_end_minutes"] <= float(threshold)).mean() if not g_other_rep.empty else np.nan
            )
        else:
            other_reported_pct = np.nan
            other_ontime_pct = np.nan

        g_dest = g[g["role"] == "destination"]
        if not g_dest.empty:
            dst_row = g_dest.sort_values("planned_arrival_end", na_position="first").iloc[-1]
            dest_reported = pd.notna(dst_row["actual_arrival"])
            dest_ontime = (dst_row["delay_end_minutes"] <= float(threshold)) if dest_reported else np.nan
        else:
            dest_reported = False
            dest_ontime = np.nan

        all_events_reported = bool(g["actual_arrival"].notna().all() and g["actual_departure"].notna().all())

        ship_rows.append({
            "shipment_id": sid,
            "carrier": ship_carrier,
            "origin_arrival_reported": bool(origin_reported),
            "origin_on_time_end": origin_ontime,
            "other_arrival_reported_pct": other_reported_pct,
            "other_on_time_end_pct": other_ontime_pct,
            "dest_arrival_reported": bool(dest_reported),
            "dest_on_time_end": dest_ontime,
            "all_events_reported": bool(all_events_reported),
        })

    ship_detail = pd.DataFrame(ship_rows)

    if ship_detail.empty:
        st.info("No shipment data after filters.")
    else:
        agg = (
            ship_detail
            .groupby("carrier", dropna=False)
            .agg(
                shipments=("shipment_id", "nunique"),
                origin_reported_pct=("origin_arrival_reported", lambda s: s.mean()*100),
                origin_on_time_end_pct=("origin_on_time_end", lambda s: s.dropna().mean()*100 if s.notna().any() else np.nan),
                other_reported_pct=("other_arrival_reported_pct", lambda s: s.dropna().mean()*100 if s.notna().any() else np.nan),
                other_on_time_end_pct=("other_on_time_end_pct", lambda s: s.dropna().mean()*100 if s.notna().any() else np.nan),
                dest_reported_pct=("dest_arrival_reported", lambda s: s.mean()*100),
                dest_on_time_end_pct=("dest_on_time_end", lambda s: s.dropna().mean()*100 if s.notna().any() else np.nan),
                all_events_reported_pct=("all_events_reported", lambda s: s.mean()*100),
            )
            .reset_index()
            .rename(columns={"carrier": "Carrier"})
        )

        ship_carrier_disp = (
            agg.assign(
                **{
                    "Arrival at origin reported (%)": agg["origin_reported_pct"].round(1),
                    "Origin arrival on-time (% of reported, planned end)": agg["origin_on_time_end_pct"].round(1),
                    "% arrival reported at other stop": agg["other_reported_pct"].round(1),
                    "% arrival at other stop on-time (% of reported, planned end)": agg["other_on_time_end_pct"].round(1),
                    "% arrival reported at destination stop": agg["dest_reported_pct"].round(1),
                    "% arrival at destination on-time (% of reported, planned end)": agg["dest_on_time_end_pct"].round(1),
                    "% shipments with ALL events reported": agg["all_events_reported_pct"].round(1),
                }
            )[
                [
                    "Carrier", "shipments",
                    "Arrival at origin reported (%)",
                    "Origin arrival on-time (% of reported, planned end)",
                    "% arrival reported at other stop",
                    "% arrival at other stop on-time (% of reported, planned end)",
                    "% arrival reported at destination stop",
                    "% arrival at destination on-time (% of reported, planned end)",
                    "% shipments with ALL events reported",
                ]
            ]
            .rename(columns={"shipments": "Number of shipments"})
            .sort_values(["Number of shipments"], ascending=False)
        )

        st.markdown("#### Coverage by Carrier")
        pretty_df(ship_carrier_disp, use_container_width=True)

        with st.expander("Per-shipment detail (planned end basis)"):
            ship_detail_disp = ship_detail.copy()

            def yes_no_na(x):
                if pd.isna(x):
                    return "N/A"
                return "Yes" if bool(x) else "No"

            ship_detail_disp = ship_detail_disp.assign(
                **{
                    "Origin arrival reported": ship_detail_disp["origin_arrival_reported"].map(yes_no_na),
                    "Origin on-time (planned end)": ship_detail_disp["origin_on_time_end"].map(yes_no_na),
                    "% other arrivals reported": (ship_detail_disp["other_arrival_reported_pct"] * 100).round(1),
                    "% other arrivals on-time (planned end)": (ship_detail_disp["other_on_time_end_pct"] * 100).round(1),
                    "Destination arrival reported": ship_detail_disp["dest_arrival_reported"].map(yes_no_na),
                    "Destination on-time (planned end)": ship_detail_disp["dest_on_time_end"].map(yes_no_na),
                    "ALL events reported": ship_detail_disp["all_events_reported"].map(yes_no_na),
                }
            )[
                [
                    "shipment_id", "carrier",
                    "Origin arrival reported", "Origin on-time (planned end)",
                    "% other arrivals reported", "% other arrivals on-time (planned end)",
                    "Destination arrival reported", "Destination on-time (planned end)",
                    "ALL events reported",
                ]
            ].rename(columns={"shipment_id": "Shipment ID", "carrier": "Carrier"})
            pretty_df(ship_detail_disp, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download shipment coverage by carrier (CSV)",
                data=ship_carrier_disp.to_csv(index=False).encode("utf-8"),
                file_name=f"shipment_coverage_carrier_{date.today().isoformat()}.csv",
                mime="text/csv",
            )
        with c2:
            st.download_button(
                "Download per-shipment detail (CSV)",
                data=ship_detail_disp.to_csv(index=False).encode("utf-8"),
                file_name=f"shipment_coverage_detail_{date.today().isoformat()}.csv",
                mime="text/csv",
            )

# =====================================================================
#                Downloads: filtered rows & Excel workbook
# =====================================================================
st.subheader("Downloads ⬇️")
cA, cB, cC = st.columns(3)
with cA:
    st.download_button(
        "Download filtered rows (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"filtered_stops_{date.today().isoformat()}.csv",
        mime="text/csv"
    )

# Pick Excel engine dynamically (robust), but prefer xlsxwriter for autosizing
try:
    import xlsxwriter  # noqa: F401
    EXCEL_ENGINE = "xlsxwriter"
    EXCEL_SUPPORTS_SET_COLUMN = True
except Exception:
    EXCEL_ENGINE = "openpyxl"
    EXCEL_SUPPORTS_SET_COLUMN = False

with cB:
    xls_buf = io.BytesIO()
    with pd.ExcelWriter(
        xls_buf, engine=EXCEL_ENGINE,
        datetime_format="yyyy-mm-dd hh:mm", date_format="yyyy-mm-dd"
    ) as writer:
        filtered.to_excel(writer, index=False, sheet_name="Filtered rows")
        if not display_grp.empty:
            display_grp.to_excel(writer, index=False, sheet_name="Carrier summary")
        if not so_disp.empty:
            so_disp.to_excel(writer, index=False, sheet_name="Stop overall")
        if not sbc_disp.empty:
            sbc_disp.to_excel(writer, index=False, sheet_name="Stop x Carrier")
        if not trend_disp.empty:
            trend_disp.to_excel(writer, index=False, sheet_name="Trends")
        if not ship_carrier_disp.empty:
            ship_carrier_disp.to_excel(writer, index=False, sheet_name="Shipment covg (carrier)")
        if not ship_detail_disp.empty:
            ship_detail_disp.to_excel(writer, index=False, sheet_name="Shipment covg (detail)")

        # Auto-fit column widths
        if EXCEL_SUPPORTS_SET_COLUMN:
            # XlsxWriter path
            for sheet_name, ws in writer.sheets.items():
                try:
                    if sheet_name == "Filtered rows":
                        df_for_ws = filtered
                    elif sheet_name == "Carrier summary":
                        df_for_ws = display_grp
                    elif sheet_name == "Stop overall":
                        df_for_ws = so_disp
                    elif sheet_name == "Stop x Carrier":
                        df_for_ws = sbc_disp
                    elif sheet_name == "Trends":
                        df_for_ws = trend_disp
                    elif sheet_name == "Shipment covg (carrier)":
                        df_for_ws = ship_carrier_disp
                    elif sheet_name == "Shipment covg (detail)":
                        df_for_ws = ship_detail_disp
                    else:
                        df_for_ws = None
                    if df_for_ws is not None and not df_for_ws.empty:
                        for i, col in enumerate(df_for_ws.columns):
                            width = min(max(10, int(df_for_ws[col].astype(str).str.len().quantile(0.9)) + 2), 60)
                            ws.set_column(i, i, width)
                except Exception:
                    pass
        else:
            # OpenPyXL fallback
            from openpyxl.utils import get_column_letter
            for sheet_name, ws in writer.sheets.items():
                try:
                    if sheet_name == "Filtered rows":
                        df_for_ws = filtered
                    elif sheet_name == "Carrier summary":
                        df_for_ws = display_grp
                    elif sheet_name == "Stop overall":
                        df_for_ws = so_disp
                    elif sheet_name == "Stop x Carrier":
                        df_for_ws = sbc_disp
                    elif sheet_name == "Trends":
                        df_for_ws = trend_disp
                    elif sheet_name == "Shipment covg (carrier)":
                        df_for_ws = ship_carrier_disp
                    elif sheet_name == "Shipment covg (detail)":
                        df_for_ws = ship_detail_disp
                    else:
                        df_for_ws = None
                    if df_for_ws is not None and not df_for_ws.empty:
                        for i, col in enumerate(df_for_ws.columns, start=1):
                            width = min(max(10, int(df_for_ws[col].astype(str).str.len().quantile(0.9)) + 2), 60)
                            ws.column_dimensions[get_column_letter(i)].width = width
                except Exception:
                    pass

    st.download_button(
        "Download Excel report (multi-sheet)",
        data=xls_buf.getvalue(),
        file_name=f"on_time_report_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with cC:
    st.info("Tip: Use Presets in the sidebar to save your filter setup for later.")

# =====================================================================
#                       Details / Diagnostics
# =====================================================================
with st.expander("Column Mapping & Data Health 🩺"):
    st.write("**Recognized columns** (Excel → internal):")
    mapped = {EXPECTED_COLUMNS[k]: col_map[k] for k in col_map}
    st.json(mapped)

    key_cols = ["stop_name", "current_carrier", "planned_arrival_start", "planned_arrival_end",
                "actual_arrival", "arrival_delta_min", "created_time", "shipment_id"]
    present_keys = [c for c in key_cols if c in filtered.columns]
    if present_keys:
        st.write("**Nulls in key columns (after filters):**")
        pretty_df(filtered[present_keys].isna().sum().to_frame("Nulls").T)
    if "arrival_delta_min" in filtered.columns:
        tmp = pd.to_numeric(filtered["arrival_delta_min"], errors="coerce")
        st.write("Non-numeric 'Stop arrival delta (minutes)' after coercion:", int(tmp.isna().sum()))
