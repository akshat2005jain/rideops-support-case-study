"""RideOps Triage & Escalation Gatekeeper (v0)
MoveInSync FDE Case Study — Zero-budget L1 intake gate, duplicate radar, and Ops Pulse.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.charts import (
    make_agent_quadrant_chart,
    make_escalation_waste_chart,
    make_handoff_penalty_chart,
    make_monthly_volume_backlog_chart,
)
from src.duplicate_radar import DuplicateRadarIndex
from src.metrics import (
    build_open_queue,
    compute_agent_performance,
    compute_category_stats,
    compute_escalation_waste,
    compute_handoff_penalty,
    compute_headline_kpis,
    compute_monthly_summary,
    compute_what_if_simulation,
    load_tickets,
)
from src.runbooks import (
    L1_CLOSURE_QUALITY_CHECKS,
    build_engineering_handoff_brief,
    build_l1_resolution_note,
    get_runbook,
)

# ---------------------------------------------------------------------------
# Page configuration & styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="RideOps Triage & Escalation Gatekeeper (v0)",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2.2rem;
        max-width: 1440px;
    }
    .ro-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        color: #F8FAFC;
        padding: 1.15rem 1.45rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.75rem;
    }
    .ro-header h1 {
        margin: 0;
        font-size: 1.45rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #FFFFFF;
    }
    .ro-header p {
        margin: 0.2rem 0 0 0;
        font-size: 0.88rem;
        color: #CBD5E1;
    }
    .ro-meta-pill {
        background: rgba(56, 189, 248, 0.16);
        border: 1px solid rgba(56, 189, 248, 0.4);
        color: #E0F2FE;
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .ro-badge {
        display: inline-block;
        padding: 0.2rem 0.58rem;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 600;
        margin-right: 0.35rem;
        margin-bottom: 0.25rem;
        border: 1px solid transparent;
    }
    .ro-badge-red { background: #FEF2F2; color: #B91C1C; border-color: #FECACA; }
    .ro-badge-amber { background: #FFFBEB; color: #B45309; border-color: #FDE68A; }
    .ro-badge-blue { background: #EFF6FF; color: #1D4ED8; border-color: #BFDBFE; }
    .ro-badge-green { background: #ECFDF5; color: #047857; border-color: #A7F3D0; }
    .ro-badge-slate { background: #F1F5F9; color: #334155; border-color: #CBD5E1; }

    .ro-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1rem 1.15rem;
        margin-bottom: 0.85rem;
    }
    .ro-card-title {
        font-size: 0.92rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 0.45rem;
    }
    .ro-desc-box {
        background: #F8FAFC;
        border-left: 3px solid #0284C7;
        padding: 0.65rem 0.85rem;
        border-radius: 0 6px 6px 0;
        font-size: 0.92rem;
        color: #0F172A;
        margin: 0.5rem 0 0.75rem 0;
    }
    .ro-gate-locked {
        background: #FEF2F2;
        border: 1px solid #FECACA;
        color: #991B1B;
        padding: 0.6rem 0.85rem;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.65rem;
    }
    .ro-gate-open {
        background: #ECFDF5;
        border: 1px solid #A7F3D0;
        color: #065F46;
        padding: 0.6rem 0.85rem;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.65rem;
    }
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 0.75rem 0.95rem;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        gap: 0.5rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

DATA_PATH = Path(__file__).resolve().parent / "rideops_support_tickets.csv"

TAB_QUEUE = "1. Live Open Queue"
TAB_GATEKEEPER = "2. Escalation Gatekeeper & Duplicate Radar"
TAB_OPS = "3. Ops Pulse & Coaching View"
ALL_TABS = [TAB_QUEUE, TAB_GATEKEEPER, TAB_OPS]

SIMULATED_PRESETS: dict[str, dict[str, str]] = {
    "Custom / Blank": {
        "category": "Roster / booking not syncing",
        "priority": "P2",
        "client_tier": "Enterprise",
        "description": "",
    },
    "Roster Cutoff Mismatch (Config Check)": {
        "category": "Roster / booking not syncing",
        "priority": "P2",
        "client_tier": "Enterprise",
        "description": "Booking cutoff changed but roster still uses old cutoff",
    },
    "Frozen Cab GPS (Telemetry Check)": {
        "category": "Live tracking / GPS incorrect",
        "priority": "P1",
        "client_tier": "Mid-market",
        "description": "Cab location frozen on map for last 20 mins",
    },
    "Report >15 Days Failing (Duplicate Check)": {
        "category": "Report export failing",
        "priority": "P3",
        "client_tier": "Enterprise",
        "description": "Report for date range > 15 days fails",
    },
    "How-To Rule Setup (L1 Deflection)": {
        "category": "How-to / feature request",
        "priority": "P4",
        "client_tier": "SMB",
        "description": "How to set female-first drop rule?",
    },
}


# ---------------------------------------------------------------------------
# Cached data & index loading
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_loaded_data(path_str: str) -> tuple[pd.DataFrame, pd.Timestamp]:
    return load_tickets(path_str)


@st.cache_resource(show_spinner=False)
def get_duplicate_radar(path_str: str) -> DuplicateRadarIndex:
    df, _ = load_tickets(path_str)
    return DuplicateRadarIndex(df)


def init_session_state(open_queue: pd.DataFrame, agents: list[str]) -> None:
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = TAB_QUEUE
    if "selected_ticket_id" not in st.session_state:
        st.session_state["selected_ticket_id"] = (
            str(open_queue.iloc[0]["ticket_id"]) if not open_queue.empty else ""
        )
    if "gatekeeper_mode" not in st.session_state:
        st.session_state["gatekeeper_mode"] = "Existing Open Ticket"
    if "active_agent" not in st.session_state:
        st.session_state["active_agent"] = agents[0] if agents else "Priya D"
    if "deflected_tickets" not in st.session_state:
        # Maps ticket_id -> action record dict
        st.session_state["deflected_tickets"] = {}
    if "verified_escalations" not in st.session_state:
        # Maps ticket_id -> action record dict
        st.session_state["verified_escalations"] = {}
    if "action_log" not in st.session_state:
        st.session_state["action_log"] = []
    if "last_generated_brief" not in st.session_state:
        st.session_state["last_generated_brief"] = None
    if "sim_counter" not in st.session_state:
        st.session_state["sim_counter"] = 1
    if "last_clicked_row_tid" not in st.session_state:
        st.session_state["last_clicked_row_tid"] = None


def jump_to_gatekeeper(ticket_id: str) -> None:
    """Switch directly to Tab 2 preloaded with the chosen open ticket."""
    st.session_state["selected_ticket_id"] = ticket_id
    st.session_state["gk_open_selector"] = ticket_id
    st.session_state["gatekeeper_mode"] = "Existing Open Ticket"
    st.session_state["active_tab"] = TAB_GATEKEEPER


def render_badges_html(row: pd.Series, session_status: str = "") -> str:
    badges: list[str] = []
    prio = str(row["priority"])
    prio_cls = "ro-badge-red" if prio == "P1" else ("ro-badge-amber" if prio == "P2" else "ro-badge-slate")
    badges.append(f'<span class="ro-badge {prio_cls}">{prio}</span>')

    status_str = str(row["status"])
    st_cls = "ro-badge-amber" if "Engineering" in status_str else "ro-badge-blue"
    badges.append(f'<span class="ro-badge {st_cls}">{status_str}</span>')

    if bool(row["is_ping_pong"]):
        badges.append(
            f'<span class="ro-badge ro-badge-red">Ping-Pong Risk ({int(row["eng_handoffs"])} handoffs)</span>'
        )
    if bool(row["is_stale"]):
        badges.append(f'<span class="ro-badge ro-badge-amber">Stale (&gt;48h: {row["age_label"]})</span>')
    if bool(row["is_reopened"]):
        badges.append(f'<span class="ro-badge ro-badge-red">Reopened ({int(row["reopen_count"])}x)</span>')
    if session_status == "Deflected at L1":
        badges.append('<span class="ro-badge ro-badge-green">Deflected at L1 (Session)</span>')
    elif session_status == "Gatekeeper Verified":
        badges.append('<span class="ro-badge ro-badge-green">Gatekeeper Verified (Session)</span>')

    return "".join(badges)


# ---------------------------------------------------------------------------
# Load data & compute live aggregates
# ---------------------------------------------------------------------------
if not DATA_PATH.exists():
    st.error(f"Dataset not found at `{DATA_PATH}`. Ensure `rideops_support_tickets.csv` is in the app folder.")
    st.stop()

df, data_pull_ts = get_loaded_data(str(DATA_PATH))
radar = get_duplicate_radar(str(DATA_PATH))
kpis = compute_headline_kpis(df)
open_queue = build_open_queue(df)
category_stats_df = compute_category_stats(df)
agents_list = sorted(df["assigned_agent"].dropna().unique().tolist())
clients_list = sorted(df["client_name"].dropna().unique().tolist())
categories_list = sorted(df["category"].dropna().unique().tolist())

init_session_state(open_queue, agents_list)

# Live session KPI reconciliation
open_ticket_ids = set(open_queue["ticket_id"].astype(str).tolist())
deflected_map: dict[str, dict[str, Any]] = st.session_state["deflected_tickets"]
verified_map: dict[str, dict[str, Any]] = st.session_state["verified_escalations"]

deflected_existing_open = sum(1 for tid in deflected_map if tid in open_ticket_ids)
total_deflected_session = len(deflected_map)
total_verified_session = len(verified_map)

live_open_backlog = max(0, kpis["open_total"] - deflected_existing_open)

# Sidebar controls (Agent identity & Reset Session)
with st.sidebar:
    st.markdown("### Workspace Controls")
    st.selectbox(
        "Active L1 Agent / Reviewer",
        options=agents_list,
        key="active_agent",
        help="Tags generated Handoff Briefs and L1 Resolution Notes.",
    )
    st.caption(
        f"Dataset: `rideops_support_tickets.csv`  \n"
        f"Rows: **{kpis['total_tickets']:,}**  \n"
        f"Data Pull: **{data_pull_ts.strftime('%d %b %Y %H:%M IST')}**"
    )
    if st.button("Reset Session Actions", width="stretch"):
        st.session_state["deflected_tickets"] = {}
        st.session_state["verified_escalations"] = {}
        st.session_state["action_log"] = []
        st.session_state["last_generated_brief"] = None
        st.rerun()

# ---------------------------------------------------------------------------
# Header & Live KPI Strip
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="ro-header">
        <div>
            <h1>🛡️ RideOps Triage &amp; Escalation Gatekeeper <span style="font-size:0.85rem;font-weight:500;opacity:0.8;">v0</span></h1>
            <p>Zero-budget L1 intake gate &amp; duplicate radar — cutting avoidable escalations, handoff ping-pong, and open backlog</p>
        </div>
        <div class="ro-meta-pill">
            Data Pull: {data_pull_ts.strftime('%d %b %Y')} &nbsp;|&nbsp; {kpis['total_tickets']:,} Tickets &nbsp;|&nbsp; Agent: {st.session_state['active_agent']}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

kpi_cols = st.columns(4)
with kpi_cols[0]:
    delta_open = f"-{deflected_existing_open} resolved in session" if deflected_existing_open else (
        f"{kpis['open_l1']} L1 | {kpis['open_eng']} Eng"
    )
    st.metric(
        "Live Open Backlog",
        f"{live_open_backlog}",
        delta=delta_open,
        delta_color="inverse" if deflected_existing_open else "off",
        help=f"Baseline open tickets as of 30 Sep 2026: {kpis['open_total']} (up +{kpis['backlog_growth_jul_sep_pct']:.1f}% since Jul EOM).",
    )
with kpi_cols[1]:
    st.metric(
        "Avoidable Escalation Rate",
        f"{kpis['avoidable_rate_pct']:.1f}%",
        delta=f"{kpis['avoidable_total']} of {kpis['escalated_total']} escalated",
        delta_color="inverse",
        help="Escalated tickets ending in Insufficient Info, Config Issue, Duplicate, Not a Bug, or Not Reproducible.",
    )
with kpi_cols[2]:
    st.metric(
        "Deflected at L1 (Session)",
        f"{total_deflected_session}",
        delta=f"{deflected_existing_open} from Open Queue" if deflected_existing_open else "Ready to triage",
        delta_color="normal" if total_deflected_session else "off",
        help="Tickets resolved cleanly at L1 with Quality Guardrail checks in this session.",
    )
with kpi_cols[3]:
    st.metric(
        "Gatekeeper-Verified Esc (Session)",
        f"{total_verified_session}",
        delta="100% preflight complete" if total_verified_session else f"Baseline penalty: {kpis['esc_penalty_multiple']:.1f}x slower",
        delta_color="normal" if total_verified_session else "off",
        help="Escalations that passed all mandatory category checks & diagnostic inputs.",
    )

# Clean horizontal tab switcher (supports 1-click jump from Tab 1 -> Tab 2)
st.radio(
    "Workspace View",
    options=ALL_TABS,
    horizontal=True,
    label_visibility="collapsed",
    key="active_tab",
)
st.divider()


# ===========================================================================
# TAB 1: LIVE OPEN QUEUE
# ===========================================================================
def render_tab_open_queue() -> None:
    st.subheader("Live Open Queue — Ranked by Urgency Score")
    st.caption(
        "All currently open tickets (`Open - with L1` and `Open - with Engineering`), prioritized by Priority, "
        "Client Tier, Age since created (relative to 30 Sep 2026 data pull), Handoff count, and Reopen status."
    )

    # Filter bar
    f1, f2, f3, f4, f5 = st.columns([1.15, 1.05, 1.05, 1.35, 1.25])
    with f1:
        status_filter = st.selectbox(
            "Status",
            options=["All Open", "Open - with L1", "Open - with Engineering"],
            key="q_status",
        )
    with f2:
        prio_filter = st.multiselect(
            "Priority",
            options=["P1", "P2", "P3", "P4"],
            default=["P1", "P2", "P3", "P4"],
            key="q_prio",
        )
    with f3:
        tier_filter = st.multiselect(
            "Client Tier",
            options=["Enterprise", "Mid-market", "SMB"],
            default=["Enterprise", "Mid-market", "SMB"],
            key="q_tier",
        )
    with f4:
        cat_filter = st.selectbox(
            "Category",
            options=["All Categories"] + categories_list,
            key="q_cat",
        )
    with f5:
        risk_filter = st.selectbox(
            "Risk Flag",
            options=[
                "All Open Tickets",
                "Ping-Pong Risk (>=2 handoffs)",
                "Stale (>48h old)",
                "Avoidable Escalation Open",
                "Reopened",
            ],
            key="q_risk",
        )

    search_query = st.text_input(
        "Search Open Queue",
        placeholder="Filter by Ticket ID (e.g. SUP-11258), Client, Agent, or Description...",
        key="q_search",
    )

    # Apply filters dynamically
    filtered = open_queue.copy()
    if status_filter != "All Open":
        filtered = filtered[filtered["status"] == status_filter]
    if prio_filter:
        filtered = filtered[filtered["priority"].isin(prio_filter)]
    if tier_filter:
        filtered = filtered[filtered["client_tier"].isin(tier_filter)]
    if cat_filter != "All Categories":
        filtered = filtered[filtered["category"] == cat_filter]
    if risk_filter == "Ping-Pong Risk (>=2 handoffs)":
        filtered = filtered[filtered["is_ping_pong"]]
    elif risk_filter == "Stale (>48h old)":
        filtered = filtered[filtered["is_stale"]]
    elif risk_filter == "Avoidable Escalation Open":
        filtered = filtered[filtered["is_avoidable_escalation"]]
    elif risk_filter == "Reopened":
        filtered = filtered[filtered["is_reopened"]]
    if search_query.strip():
        q_low = search_query.strip().lower()
        mask = (
            filtered["ticket_id"].str.lower().str.contains(q_low, na=False, regex=False)
            | filtered["client_name"].str.lower().str.contains(q_low, na=False, regex=False)
            | filtered["description"].str.lower().str.contains(q_low, na=False, regex=False)
            | filtered["assigned_agent"].str.lower().str.contains(q_low, na=False, regex=False)
            | filtered["category"].str.lower().str.contains(q_low, na=False, regex=False)
        )
        filtered = filtered[mask]

    filtered = filtered.reset_index(drop=True)

    # Add session action state column
    def _sess_state(tid: str) -> str:
        if tid in deflected_map:
            return "Deflected at L1"
        if tid in verified_map:
            return "Gatekeeper Verified"
        return "Pending Triage"

    filtered["session_action"] = filtered["ticket_id"].map(_sess_state)

    # Compact summary strip
    pp_cnt = int(filtered["is_ping_pong"].sum()) if not filtered.empty else 0
    stale_cnt = int(filtered["is_stale"].sum()) if not filtered.empty else 0
    reopen_cnt = int(filtered["is_reopened"].sum()) if not filtered.empty else 0
    st.markdown(
        f"""
        <div style="margin: 0.25rem 0 0.75rem 0;">
            <span class="ro-badge ro-badge-slate">Showing {len(filtered)} of {len(open_queue)} open tickets</span>
            <span class="ro-badge ro-badge-red">Ping-Pong Risk (&ge;2 handoffs): {pp_cnt}</span>
            <span class="ro-badge ro-badge-amber">Stale (&gt;48h): {stale_cnt}</span>
            <span class="ro-badge ro-badge-blue">Reopened Open: {reopen_cnt}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filtered.empty:
        st.info("No open tickets match the current filter combination. Clear filters to view the full queue.")
        return

    col_queue, col_panel = st.columns([1.35, 1.0], gap="large")

    with col_queue:
        display_df = filtered[
            [
                "urgency_score",
                "ticket_id",
                "priority",
                "client_name",
                "client_tier",
                "category",
                "status",
                "age_label",
                "eng_handoffs",
                "risk_badges",
                "session_action",
            ]
        ].rename(
            columns={
                "urgency_score": "Urgency",
                "ticket_id": "Ticket ID",
                "priority": "Prio",
                "client_name": "Client",
                "client_tier": "Tier",
                "category": "Category",
                "status": "Status",
                "age_label": "Age",
                "eng_handoffs": "Handoffs",
                "risk_badges": "Risk Flags",
                "session_action": "Session State",
            }
        )

        selection_event = st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            height=470,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Urgency": st.column_config.ProgressColumn(
                    "Urgency",
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                ),
                "Handoffs": st.column_config.NumberColumn("Handoffs", format="%d"),
            },
        )

        # Resolve selected ticket: fresh dataframe row click updates picker state,
        # while subsequent manual dropdown changes are preserved without clobbering.
        filtered_ids = filtered["ticket_id"].astype(str).tolist()
        selected_rows = (
            selection_event.selection.rows
            if selection_event and hasattr(selection_event, "selection")
            else []
        )
        if selected_rows:
            row_idx = selected_rows[0]
            if 0 <= row_idx < len(filtered):
                clicked_tid = str(filtered.iloc[row_idx]["ticket_id"])
                if clicked_tid != st.session_state.get("last_clicked_row_tid"):
                    st.session_state["last_clicked_row_tid"] = clicked_tid
                    st.session_state["selected_ticket_id"] = clicked_tid
                    st.session_state["queue_ticket_picker"] = clicked_tid
        else:
            st.session_state["last_clicked_row_tid"] = None

        current_tid = st.session_state.get("queue_ticket_picker") or st.session_state.get(
            "selected_ticket_id", filtered_ids[0]
        )
        if current_tid not in filtered_ids:
            current_tid = filtered_ids[0]
            st.session_state["queue_ticket_picker"] = current_tid
        elif "queue_ticket_picker" not in st.session_state:
            st.session_state["queue_ticket_picker"] = current_tid

        chosen_tid = st.selectbox(
            "Or pick a ticket directly to inspect in the Triage Panel",
            options=filtered_ids,
            format_func=lambda tid: (
                f"{tid} | {filtered.loc[filtered['ticket_id'] == tid, 'priority'].iloc[0]} | "
                f"{filtered.loc[filtered['ticket_id'] == tid, 'client_name'].iloc[0]} — "
                f"{filtered.loc[filtered['ticket_id'] == tid, 'category'].iloc[0]}"
            ),
            key="queue_ticket_picker",
        )
        st.session_state["selected_ticket_id"] = chosen_tid

        with st.expander("How Urgency Score (0-100) is calculated"):
            st.markdown(
                """
                - **Priority:** `P1 = +40`, `P2 = +28`, `P3 = +15`, `P4 = +5`
                - **Client Tier:** `Enterprise = +25`, `Mid-market = +15`, `SMB = +8`
                - **Age Penalty:** `+3 pts per day open` relative to 30 Sep 2026 data pull (capped at `+20`)
                - **Ping-Pong Penalty:** `+5 pts per Engineering handoff` (capped at `+15`), plus `+5` if reopened
                """
            )

    with col_panel:
        row = filtered[filtered["ticket_id"] == st.session_state["selected_ticket_id"]].iloc[0]
        tid = str(row["ticket_id"])
        sess_state = _sess_state(tid)

        st.markdown("#### Triage & Gatekeeper Preview")
        st.markdown(render_badges_html(row, sess_state), unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="ro-card">
                <div class="ro-card-title">{tid} &mdash; {row['client_name']} ({row['client_tier']})</div>
                <div style="font-size:0.83rem;color:#475569;line-height:1.55;">
                    <b>Category:</b> {row['category']}<br/>
                    <b>Assigned Agent:</b> {row['assigned_agent']} &nbsp;|&nbsp; <b>Channel:</b> {row['channel']}<br/>
                    <b>Created:</b> {row['created_at'].strftime('%d %b %Y %H:%M IST')} &nbsp;|&nbsp; <b>Urgency:</b> {row['urgency_score']:.0f}/100<br/>
                    <b>Linked ENG Ticket:</b> {row['eng_ticket_id'] if row['eng_ticket_id'] else 'None (Not yet escalated)'}
                    {f" &nbsp;|&nbsp; <b>Last Verdict:</b> {row['eng_outcome']}" if row['eng_outcome'] else ""}
                </div>
                <div class="ro-desc-box">"{row['description']}"</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Category historical avoidable risk
        cat_row = category_stats_df[category_stats_df["category"] == row["category"]]
        if not cat_row.empty:
            cr = cat_row.iloc[0]
            st.caption(
                f"Category baseline ({row['category']}): **{cr['escalation_rate_pct']:.1f}%** escalation rate, "
                f"**{cr['avoidable_of_esc_pct']:.1f}%** of escalations were avoidable."
            )

        # Quick Duplicate Radar Preview
        radar_preview = radar.search(
            description=str(row["description"]),
            category=str(row["category"]),
            exclude_ticket_id=tid,
            top_k=3,
        )
        st.markdown("**Quick Duplicate Radar Preview**")
        if radar_preview.risk_level == "high":
            st.error(radar_preview.recommendation)
        elif radar_preview.risk_level == "medium":
            st.warning(radar_preview.recommendation)
        else:
            st.info(radar_preview.recommendation)

        if not radar_preview.matches.empty:
            st.dataframe(
                radar_preview.matches[["eng_ticket_id", "similarity_pct", "eng_outcome", "description"]].rename(
                    columns={
                        "eng_ticket_id": "ENG ID",
                        "similarity_pct": "Match %",
                        "eng_outcome": "Past Verdict",
                        "description": "Historical Issue",
                    }
                ),
                width="stretch",
                hide_index=True,
                height=145,
            )

        st.button(
            f"Run Full Escalation Gatekeeper for {tid} →",
            type="primary",
            width="stretch",
            on_click=jump_to_gatekeeper,
            args=(tid,),
        )


# ===========================================================================
# TAB 2: ESCALATION GATEKEEPER & DUPLICATE RADAR
# ===========================================================================
def render_tab_gatekeeper() -> None:
    st.subheader("Escalation Gatekeeper & Duplicate Radar")
    st.caption(
        "Mandatory L1 intake workflow: scan past Engineering tickets for duplicates, verify category config checks, "
        "and either resolve cleanly at L1 (with closure guardrails) or emit a complete Engineering Handoff Brief."
    )

    mode = st.radio(
        "Ticket Source",
        options=["Existing Open Ticket", "Simulate New Incoming Ticket"],
        horizontal=True,
        key="gatekeeper_mode",
    )

    active_ticket: dict[str, Any]
    exclude_tid: str | None = None

    if mode == "Existing Open Ticket":
        open_ids = open_queue["ticket_id"].astype(str).tolist()
        current_tid = st.session_state.get("gk_open_selector") or st.session_state.get(
            "selected_ticket_id", open_ids[0]
        )
        if current_tid not in open_ids:
            current_tid = open_ids[0]
        st.session_state["gk_open_selector"] = current_tid

        chosen_tid = st.selectbox(
            "Select Open Ticket to Triage",
            options=open_ids,
            format_func=lambda tid: (
                f"{tid} | {open_queue.loc[open_queue['ticket_id'] == tid, 'priority'].iloc[0]} | "
                f"{open_queue.loc[open_queue['ticket_id'] == tid, 'client_name'].iloc[0]} | "
                f"{open_queue.loc[open_queue['ticket_id'] == tid, 'category'].iloc[0]} — "
                f"{open_queue.loc[open_queue['ticket_id'] == tid, 'description'].iloc[0][:55]}"
            ),
            key="gk_open_selector",
        )
        st.session_state["selected_ticket_id"] = chosen_tid
        row = open_queue[open_queue["ticket_id"] == chosen_tid].iloc[0]
        exclude_tid = chosen_tid
        active_ticket = {
            "ticket_id": chosen_tid,
            "client_name": str(row["client_name"]),
            "client_tier": str(row["client_tier"]),
            "category": str(row["category"]),
            "priority": str(row["priority"]),
            "description": str(row["description"]),
            "status": str(row["status"]),
            "eng_handoffs": int(row["eng_handoffs"]),
            "eng_ticket_id": str(row["eng_ticket_id"]),
            "eng_outcome": str(row["eng_outcome"]),
            "is_existing_open": True,
        }

        sess_state = (
            "Deflected at L1"
            if chosen_tid in deflected_map
            else ("Gatekeeper Verified" if chosen_tid in verified_map else "")
        )
        st.markdown(render_badges_html(row, sess_state), unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="ro-desc-box">
                <b>{active_ticket['ticket_id']}</b> &bull; {active_ticket['client_name']} ({active_ticket['client_tier']})
                &bull; <b>{active_ticket['category']}</b><br/>
                "{active_ticket['description']}"
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        preset_col, _ = st.columns([1.4, 2.0])
        with preset_col:
            preset_name = st.selectbox(
                "Load Realistic Demo Scenario (Optional)",
                options=list(SIMULATED_PRESETS.keys()),
                key="sim_preset_select",
            )
        preset = SIMULATED_PRESETS[preset_name]

        c1, c2, c3, c4 = st.columns([1.3, 0.9, 1.5, 0.7])
        with c1:
            sim_client = st.selectbox("Client", options=clients_list, key="sim_client")
        with c2:
            tier_opts = ["Enterprise", "Mid-market", "SMB"]
            sim_tier = st.selectbox(
                "Client Tier",
                options=tier_opts,
                index=tier_opts.index(preset["client_tier"]),
                key=f"sim_tier_{preset_name}",
            )
        with c3:
            sim_cat = st.selectbox(
                "Category",
                options=categories_list,
                index=categories_list.index(preset["category"]) if preset["category"] in categories_list else 0,
                key=f"sim_cat_{preset_name}",
            )
        with c4:
            prio_opts = ["P1", "P2", "P3", "P4"]
            sim_prio = st.selectbox(
                "Priority",
                options=prio_opts,
                index=prio_opts.index(preset["priority"]),
                key=f"sim_prio_{preset_name}",
            )
        sim_desc = st.text_area(
            "Issue Description",
            value=preset["description"],
            placeholder="Describe what the client transport admin reported (e.g., 'Booking cutoff changed but roster still uses old cutoff')...",
            height=78,
            key=f"sim_desc_{preset_name}",
        )
        active_ticket = {
            "ticket_id": f"SIM-{1000 + st.session_state['sim_counter']}",
            "client_name": sim_client,
            "client_tier": sim_tier,
            "category": sim_cat,
            "priority": sim_prio,
            "description": sim_desc.strip(),
            "status": "New Intake (L1)",
            "eng_handoffs": 0,
            "eng_ticket_id": "",
            "eng_outcome": "",
            "is_existing_open": False,
        }

    # Category historical stats context bar
    cat_stat = category_stats_df[category_stats_df["category"] == active_ticket["category"]]
    if not cat_stat.empty:
        cs = cat_stat.iloc[0]
        st.caption(
            f"**Historical {active_ticket['category']} Profile:** {cs['total_tickets']} tickets ({cs['share_pct']:.1f}% of volume) | "
            f"Escalation Rate: **{cs['escalation_rate_pct']:.1f}%** | Avoidable Share of Escalations: **{cs['avoidable_of_esc_pct']:.1f}%** | "
            f"Past Duplicate Escalations: **{cs['duplicate_count']}**"
        )

    # -----------------------------------------------------------------------
    # STEP A: DUPLICATE & KNOWN-ISSUE RADAR
    # -----------------------------------------------------------------------
    st.markdown("### Step A — Duplicate & Known-Issue Radar")
    radar_res = radar.search(
        description=active_ticket["description"],
        category=active_ticket["category"],
        exclude_ticket_id=exclude_tid,
        top_k=5,
    )

    if radar_res.risk_level == "high":
        st.error(radar_res.recommendation)
    elif radar_res.risk_level == "medium":
        st.warning(radar_res.recommendation)
    else:
        st.info(radar_res.recommendation)

    linked_eng_ids: list[str] = []
    if not radar_res.matches.empty:
        rm1, rm2, rm3, rm4 = st.columns(4)
        rm1.metric("Similar Historical Escalations", f"{radar_res.total_similar_count}")
        rm2.metric("Avoidable Verdict Share", f"{radar_res.avoidable_share_pct:.1f}%")
        rm3.metric("Past 'Duplicate' Verdicts", f"{radar_res.duplicate_count}")
        rm4.metric("Top Historical Verdict", radar_res.top_outcome)

        st.dataframe(
            radar_res.matches[
                ["similarity_pct", "eng_ticket_id", "ticket_id", "eng_outcome", "eng_handoffs", "client_name", "description"]
            ].rename(
                columns={
                    "similarity_pct": "Match %",
                    "eng_ticket_id": "ENG Ticket ID",
                    "ticket_id": "Support ID",
                    "eng_outcome": "Past Eng Verdict",
                    "eng_handoffs": "Handoffs",
                    "client_name": "Client",
                    "description": "Matched Description",
                }
            ),
            width="stretch",
            hide_index=True,
            height=215,
        )

        top_eng_options = radar_res.matches["eng_ticket_id"].tolist()
        linked_eng_ids = st.multiselect(
            "Link Related / Duplicate ENG Ticket ID(s) to Brief or L1 Resolution",
            options=top_eng_options,
            default=top_eng_options[:1] if radar_res.matches.iloc[0]["similarity_pct"] >= 80.0 else [],
            key=f"link_eng_{active_ticket['ticket_id']}_{active_ticket['category']}",
        )

    # -----------------------------------------------------------------------
    # STEP B: CATEGORY-SPECIFIC L1 RUNBOOK & MANDATORY PREFLIGHT CHECKS
    # -----------------------------------------------------------------------
    runbook = get_runbook(active_ticket["category"])
    st.markdown(f"### Step B — L1 Runbook & Mandatory Preflight Checks (`{runbook.category}`)")

    col_runbook, col_checks = st.columns([0.95, 1.35], gap="large")
    with col_runbook:
        fixes_md = "\n".join(f"- {step}" for step in runbook.common_l1_fixes)
        st.markdown(
            f"""
            <div class="ro-card">
                <div class="ro-card-title">L1 Triage Goal</div>
                <p style="font-size:0.86rem;color:#334155;margin-bottom:0.65rem;">{runbook.l1_triage_goal}</p>
                <div class="ro-card-title">Try These L1 Fixes First</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(fixes_md)
        st.caption(f"**Escalation Bar:** {runbook.escalation_criteria}")

    widget_ns = f"{active_ticket['ticket_id']}_{runbook.category}"
    checked_items: list[str] = []
    diagnostics_payload: dict[str, str] = {}

    with col_checks:
        st.markdown("**1. Mandatory Preflight Verification Checks**")
        for idx, check_text in enumerate(runbook.mandatory_checks):
            is_checked = st.checkbox(check_text, key=f"chk_{widget_ns}_{idx}")
            if is_checked:
                checked_items.append(check_text)

        st.markdown("**2. Mandatory Diagnostic Payload (Required by Engineering)**")
        for field in runbook.diagnostic_fields:
            val = st.text_input(
                field.label,
                placeholder=field.placeholder,
                help=field.help_text,
                key=f"diag_{widget_ns}_{field.key}",
            )
            diagnostics_payload[field.key] = val

        total_reqs = len(runbook.mandatory_checks) + len(runbook.diagnostic_fields)
        filled_diag = sum(1 for v in diagnostics_payload.values() if v.strip())
        completed_reqs = len(checked_items) + filled_diag
        st.progress(
            completed_reqs / total_reqs if total_reqs else 0.0,
            text=f"Preflight Readiness: {len(checked_items)}/{len(runbook.mandatory_checks)} checks & "
            f"{filled_diag}/{len(runbook.diagnostic_fields)} diagnostic fields complete",
        )

    all_checks_done = len(checked_items) == len(runbook.mandatory_checks)
    all_fields_done = all(v.strip() != "" for v in diagnostics_payload.values())
    has_description = bool(active_ticket["description"].strip())
    gate_passed = all_checks_done and all_fields_done and has_description

    # -----------------------------------------------------------------------
    # STEP C: HARD ESCALATION GATE vs QUALITY-CHECKED L1 RESOLUTION
    # -----------------------------------------------------------------------
    st.markdown("### Step C — Action Decision: Escalate (Hard Gate) or Resolve at L1")
    col_esc, col_l1 = st.columns(2, gap="large")

    with col_esc:
        st.markdown("#### Path 1: Escalate to Engineering (Hard Gate)")
        if gate_passed:
            st.markdown(
                '<div class="ro-gate-open">🔓 GATE UNLOCKED — All mandatory preflight checks & diagnostic inputs verified.</div>',
                unsafe_allow_html=True,
            )
        else:
            missing_parts: list[str] = []
            if not has_description:
                missing_parts.append("issue description")
            if not all_checks_done:
                missing_parts.append(f"{len(runbook.mandatory_checks) - len(checked_items)} preflight check(s)")
            if not all_fields_done:
                missing_parts.append(f"{len(runbook.diagnostic_fields) - filled_diag} diagnostic field(s)")
            st.markdown(
                f'<div class="ro-gate-locked">🔒 GATE LOCKED — Still missing: {", ".join(missing_parts)}.</div>',
                unsafe_allow_html=True,
            )

        extra_notes = st.text_input(
            "Additional L1 Notes for Engineering (Optional)",
            placeholder="e.g., Client escalation SLA is 2 hrs; admin available on phone.",
            key=f"esc_notes_{widget_ns}",
        )

        esc_clicked = st.button(
            "Generate Engineering Escalation Ticket",
            type="primary",
            disabled=not gate_passed,
            width="stretch",
            key=f"btn_escalate_{widget_ns}",
        )

        if esc_clicked and gate_passed:
            brief = build_engineering_handoff_brief(
                ticket=active_ticket,
                checked_items=checked_items,
                diagnostics=diagnostics_payload,
                linked_eng_ids=linked_eng_ids,
                l1_agent=st.session_state["active_agent"],
                notes=extra_notes,
            )
            tid = active_ticket["ticket_id"]
            record = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "ticket_id": tid,
                "action": "Gatekeeper-Verified Escalation",
                "category": active_ticket["category"],
                "client": active_ticket["client_name"],
                "agent": st.session_state["active_agent"],
                "linked_eng": ", ".join(linked_eng_ids) if linked_eng_ids else "None",
            }
            st.session_state["verified_escalations"][tid] = record
            st.session_state["deflected_tickets"].pop(tid, None)
            st.session_state["action_log"].insert(0, record)
            st.session_state["last_generated_brief"] = {
                "kind": "escalation",
                "ticket_id": tid,
                "text": brief,
            }
            if not active_ticket["is_existing_open"]:
                st.session_state["sim_counter"] += 1
            st.rerun()

    with col_l1:
        st.markdown("#### Path 2: Resolve at L1 (Config Fix / How-To / Duplicate)")
        st.caption(
            "Avoid escalating non-bugs, config issues, or duplicates — while enforcing a Closure Quality Check "
            "so tickets cannot be prematurely closed and reopened."
        )
        res_type = st.selectbox(
            "L1 Resolution Path",
            options=[
                "Config Fix Applied at L1",
                "Linked to Known Existing ENG Ticket (Avoided Duplicate)",
                "How-To / KB Guide Walkthrough",
                "Operational / Vendor Dispatch Handled (Non-Bug)",
            ],
            key=f"l1_res_type_{widget_ns}",
        )
        closure_checks_passed = 0
        for c_idx, c_label in enumerate(L1_CLOSURE_QUALITY_CHECKS):
            if st.checkbox(c_label, key=f"l1_close_chk_{widget_ns}_{c_idx}"):
                closure_checks_passed += 1

        res_summary = st.text_input(
            "Verified Resolution Summary (Required for Closure Quality)",
            placeholder="e.g., Updated shift cutoff to T-4h, ran manual roster sync, confirmed 6 AM shift reflects for client.",
            key=f"l1_res_sum_{widget_ns}",
        )
        l1_ready = (
            closure_checks_passed == len(L1_CLOSURE_QUALITY_CHECKS)
            and bool(res_summary.strip())
            and has_description
        )

        l1_clicked = st.button(
            "Resolve at L1 with Config Fix / How-To",
            type="secondary",
            disabled=not l1_ready,
            width="stretch",
            key=f"btn_resolve_l1_{widget_ns}",
        )

        if l1_clicked and l1_ready:
            note = build_l1_resolution_note(
                ticket=active_ticket,
                resolution_type=res_type,
                resolution_summary=res_summary,
                linked_eng_ids=linked_eng_ids,
                l1_agent=st.session_state["active_agent"],
            )
            tid = active_ticket["ticket_id"]
            record = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "ticket_id": tid,
                "action": f"Deflected at L1 ({res_type})",
                "category": active_ticket["category"],
                "client": active_ticket["client_name"],
                "agent": st.session_state["active_agent"],
                "linked_eng": ", ".join(linked_eng_ids) if linked_eng_ids else "None",
            }
            st.session_state["deflected_tickets"][tid] = record
            st.session_state["verified_escalations"].pop(tid, None)
            st.session_state["action_log"].insert(0, record)
            st.session_state["last_generated_brief"] = {
                "kind": "l1_resolution",
                "ticket_id": tid,
                "text": note,
            }
            if not active_ticket["is_existing_open"]:
                st.session_state["sim_counter"] += 1
            st.rerun()

    # -----------------------------------------------------------------------
    # STEP D: STRUCTURED HANDOFF BRIEF / RESOLUTION OUTPUT & SESSION LOG
    # -----------------------------------------------------------------------
    last_out = st.session_state.get("last_generated_brief")
    if last_out:
        st.markdown("### Step D — Generated Handoff Brief / Resolution Record")
        if last_out["kind"] == "escalation":
            st.success(
                f"Gatekeeper-verified Engineering Escalation Brief generated for **{last_out['ticket_id']}**. "
                "Copy directly into Jira / Engineering queue:"
            )
        else:
            st.success(
                f"Ticket **{last_out['ticket_id']}** deflected & quality-resolved at L1! "
                "Live Open Backlog and Deflection KPIs updated above."
            )
        st.code(last_out["text"], language=None)

    if st.session_state["action_log"]:
        with st.expander(f"Session Triage Log ({len(st.session_state['action_log'])} actioned)", expanded=False):
            st.dataframe(
                pd.DataFrame(st.session_state["action_log"]),
                width="stretch",
                hide_index=True,
            )


# ===========================================================================
# TAB 3: OPS PULSE & COACHING VIEW
# ===========================================================================
def render_tab_ops_pulse() -> None:
    st.subheader("Ops Pulse & Coaching View — Meera & Ritika's Weekly Review")
    st.caption(
        "Every chart and simulator baseline below is computed live from `rideops_support_tickets.csv` — "
        "connecting backlog growth to avoidable escalations, handoff ping-pong, and agent coaching opportunities."
    )

    monthly_df = compute_monthly_summary(df)
    waste_df = compute_escalation_waste(df)
    handoff_df = compute_handoff_penalty(df)
    agent_df = compute_agent_performance(df)

    # North Star & Guardrail KPI Strip
    ns1, ns2, ns3, ns4 = st.columns(4)
    ns1.metric(
        "True FCR Rate (L1, No Reopen)",
        f"{kpis['true_fcr_closed_pct']:.1f}%",
        delta=f"{kpis['true_fcr_count']} of {kpis['closed_total']} closed",
        delta_color="off",
        help="North Star: Closed tickets resolved by L1 without escalation and without reopening.",
    )
    ns2.metric(
        "Jul → Sep Volume / Backlog",
        f"+{kpis['vol_growth_jul_sep_pct']:.1f}% / +{kpis['backlog_growth_jul_sep_pct']:.1f}%",
        delta=f"{kpis['jul_tickets']}→{kpis['sep_tickets']} vol | {kpis['open_eom_jul']}→{kpis['open_eom_sep']} open",
        delta_color="inverse",
    )
    ns3.metric(
        "Escalation Penalty Multiple",
        f"{kpis['esc_penalty_multiple']:.1f}x",
        delta=f"{kpis['median_esc_hrs']:.1f}h esc vs {kpis['median_non_esc_hrs']:.1f}h L1",
        delta_color="inverse",
    )
    ns4.metric(
        "Reopen Rate (Guardrail <8%)",
        f"{kpis['reopen_rate_all_pct']:.2f}%",
        delta=f"{kpis['reopened_total']}/{kpis['total_tickets']} all ({kpis['reopen_rate_closed_pct']:.2f}% closed) | CSAT {kpis['mean_csat']:.2f}",
        delta_color="inverse" if kpis["reopen_rate_all_pct"] >= 8.0 else "normal",
    )

    # 2x2 Executive Plotly Charts
    r1c1, r1c2 = st.columns(2, gap="medium")
    with r1c1:
        st.plotly_chart(make_monthly_volume_backlog_chart(monthly_df), width="stretch")
    with r1c2:
        st.plotly_chart(make_escalation_waste_chart(waste_df), width="stretch")

    r2c1, r2c2 = st.columns(2, gap="medium")
    with r2c1:
        st.plotly_chart(make_handoff_penalty_chart(handoff_df), width="stretch")
    with r2c2:
        st.plotly_chart(make_agent_quadrant_chart(agent_df), width="stretch")

    # Dynamic Coaching Spotlight Cards (computed live from agent_df)
    top_reopener = agent_df.sort_values(by="reopen_rate_pct", ascending=False).iloc[0]
    top_escalator = agent_df.sort_values(by="escalation_rate_pct", ascending=False).iloc[0]
    total_howto_all = int(agent_df["how_to_esc_count"].sum())
    howto_share_pct = (
        round((top_escalator["how_to_esc_count"] / total_howto_all) * 100.0, 1) if total_howto_all else 0.0
    )

    cc1, cc2 = st.columns(2, gap="medium")
    with cc1:
        st.warning(
            f"**Coaching Priority 1 — Premature Closures ({top_reopener['assigned_agent']}):** "
            f"Fastest median first-close (**{top_reopener['median_first_close_hrs']:.1f}h**), "
            f"but **{top_reopener['reopen_rate_pct']:.1f}%** reopen rate and lowest CSAT (**{top_reopener['mean_csat']:.2f}/5**). "
            "Fix: Enforce Gatekeeper's Closure Quality Guardrail & track Reopen Rate < 8%."
        )
    with cc2:
        st.error(
            f"**Coaching Priority 2 — Over-Escalation ({top_escalator['assigned_agent']}):** "
            f"**{top_escalator['escalation_rate_pct']:.1f}%** escalation rate with "
            f"**{top_escalator['avoidable_of_esc_pct']:.1f}%** avoidable, accounting for "
            f"**{int(top_escalator['how_to_esc_count'])} of {total_howto_all} ({howto_share_pct:.0f}%)** "
            "of all 'Not a bug - how-to' escalations. Fix: Mandatory Gatekeeper preflight + KB runbooks."
        )

    with st.expander("Full L1 Agent Scorecard (All Agents)", expanded=False):
        st.dataframe(
            agent_df[
                [
                    "assigned_agent",
                    "coaching_flag",
                    "total_tickets",
                    "open_tickets",
                    "escalation_rate_pct",
                    "avoidable_of_esc_pct",
                    "how_to_esc_count",
                    "median_first_close_hrs",
                    "reopen_rate_pct",
                    "mean_csat",
                ]
            ].rename(
                columns={
                    "assigned_agent": "Agent",
                    "coaching_flag": "Coaching Profile",
                    "total_tickets": "Tickets",
                    "open_tickets": "Open",
                    "escalation_rate_pct": "Esc %",
                    "avoidable_of_esc_pct": "Avoidable % of Esc",
                    "how_to_esc_count": "How-To Esc",
                    "median_first_close_hrs": "Med 1st-Close (h)",
                    "reopen_rate_pct": "Reopen %",
                    "mean_csat": "Avg CSAT",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    st.divider()

    # -----------------------------------------------------------------------
    # INTERACTIVE WHAT-IF IMPACT SIMULATOR ($0 NEW HIRING PLAN)
    # -----------------------------------------------------------------------
    st.markdown("### Interactive What-If Impact Simulator — Ritika's $0 Hiring Lever")
    st.caption(
        "Simulate the operational impact of cutting avoidable escalations via the Escalation Gatekeeper & Duplicate Radar "
        "and curbing premature closures via the Closure Quality Guardrail — without adding headcount."
    )

    sim_ctrl1, sim_ctrl2, sim_ctrl3 = st.columns([1.5, 1.3, 1.0], gap="medium")
    with sim_ctrl1:
        reduction_pct = st.slider(
            "Target Reduction in Avoidable Escalations (%)",
            min_value=0,
            max_value=80,
            value=50,
            step=5,
            format="%d%%",
            key="whatif_reduction_slider",
        )
    with sim_ctrl2:
        reopen_red_pct = st.slider(
            "Target Reduction in Premature Reopens (%)",
            min_value=0,
            max_value=60,
            value=30,
            step=5,
            format="%d%%",
            key="whatif_reopen_slider",
            help="Driven by the Closure Quality Guardrail + Karan B coaching (set to 0% for escalation-only impact).",
        )
    with sim_ctrl3:
        active_hrs_per_ho = st.number_input(
            "Assumed Active Eng+L1 Hrs / Handoff",
            min_value=0.5,
            max_value=4.0,
            value=1.5,
            step=0.25,
            key="whatif_eng_hrs_input",
            help="Explicit active engineering/support investigation effort per avoidable handoff.",
        )

    sim = compute_what_if_simulation(
        df,
        reduction_pct=float(reduction_pct),
        reopen_reduction_pct=float(reopen_red_pct),
        eng_active_hrs_per_handoff=float(active_hrs_per_ho),
    )

    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric(
        "Projected Open Backlog (Steady-State)",
        f"{sim['littles_law_after']:.1f} open",
        delta=f"-{sim['littles_law_saved']:.1f} Little's Law (-{sim['littles_law_reduction_pct']:.1f}%) | Direct: {sim['direct_open_after']:.0f}"
        if (sim["littles_law_saved"] > 0 or sim["direct_open_saved"] > 0)
        else f"Baseline ({sim['current_open_total']} open)",
        delta_color="inverse" if sim["littles_law_saved"] > 0 else "off",
        help=f"Little's Law steady-state open backlog at Sep arrival rate; Direct snapshot removes deflected avoidable tickets from the {sim['current_open_avoidable']} currently open avoidable escalations.",
    )
    sm2.metric(
        "Avoidable Esc. Deflected (Sep Run-Rate)",
        f"{sim['deflected_sep_mo']:.1f} / mo",
        delta=f"{sim['deflected_qtr']:.1f}/qtr | Avoidable: {sim['current_avoidable_rate_pct']:.1f}% → {sim['new_avoidable_rate_pct']:.1f}%",
        delta_color="normal" if sim["deflected_qtr"] > 0 else "off",
    )
    sm3.metric(
        "Elapsed Queue Hours Reclaimed",
        f"{sim['elapsed_hrs_saved_total_sep']:,.1f} h/mo",
        delta=f"{sim['elapsed_hrs_saved_total_qtr']:,.1f} h/qtr (-{sim['avg_resolution_delta_w']:.1f}h avg wait)",
        delta_color="normal" if sim["elapsed_hrs_saved_total_sep"] > 0 else "off",
    )
    sm4.metric(
        "Active Eng+L1 Triage Hours Saved",
        f"{sim['eng_active_hrs_saved_mo']:.1f} h/mo",
        delta=f"{sim['eng_active_hrs_saved_qtr']:.1f} h/qtr at $0 hiring cost",
        delta_color="normal" if sim["eng_active_hrs_saved_qtr"] > 0 else "off",
    )

    with st.expander("Transparent Formulas & CSV Baselines Behind This Simulation"):
        st.markdown(
            f"""
            Every baseline figure below is computed directly from `rideops_support_tickets.csv` and aligns 1:1 with `analysis/metrics_summary.json`:
            1. **Avoidable Escalations Deflected:** `{sim['total_avoidable_qtr']}` quarterly avoidable escalations &times; `{reduction_pct}%` = **`{sim['deflected_qtr']:.1f}` tickets/quarter** (`{sim['sep_avoidable']}` Sep avoidable &times; `{reduction_pct}%` = **`{sim['deflected_sep_mo']:.1f}`/month**).
               Company escalation rate drops to **`{sim['new_esc_rate_pct']:.2f}%`** and avoidable share of escalations drops from **`{sim['current_avoidable_rate_pct']:.2f}%` &rarr; `{sim['new_avoidable_rate_pct']:.2f}%`**.
            2. **Elapsed Queue / Client Wait Hours Saved:**
               - Avoidable escalations carry **`{sim['excess_hrs_per_avoidable']:.2f}h`** mean excess elapsed time vs L1 resolution (`{kpis['mean_avoidable_hrs']:.2f}h - {kpis['mean_non_esc_hrs']:.2f}h` computed live): `{sim['deflected_sep_mo']:.1f} × {sim['excess_hrs_per_avoidable']:.2f}h = {sim['elapsed_hrs_saved_avoid_sep']:,.1f} hrs/mo` (`{sim['elapsed_hrs_saved_avoid_qtr']:,.1f} hrs/qtr`).
               - Reopened tickets add **`{sim['reopen_extra_hrs']:.2f}h`** mean extra elapsed time after first close: cutting `{reopen_red_pct}%` of `{sim['sep_reopened']}` Sep reopens saves `{sim['elapsed_hrs_saved_reopen_sep']:,.1f} hrs/mo` (`{sim['elapsed_hrs_saved_reopen_qtr']:,.1f} hrs/qtr`).
               - **Total:** **`{sim['elapsed_hrs_saved_total_sep']:,.1f} elapsed hrs/mo`** (reducing mean ticket turnaround by **`{sim['avg_resolution_delta_w']:.2f}h`**).
            3. **Projected Open Backlog Reduction (Two Complementary Methods):**
               - **Little's Law Steady-State (`L = λ × W`):** At Sep arrival rate `λ = {sim['sep_arrival_rate_per_hour']:.4f} tickets/hr` ({sim['sep_tickets']} / 720h), cutting mean residence time `ΔW = {sim['avg_resolution_delta_w']:.2f}h` reduces steady-state open backlog by **`-{sim['littles_law_saved']:.1f}` tickets** (`{sim['current_open_total']} → {sim['littles_law_after']:.1f}`, **`-{sim['littles_law_reduction_pct']:.2f}%`**).
               - **Direct Sep-30 Snapshot Attribution:** `{sim['current_open_avoidable']}` of the `{sim['current_open_total']}` open tickets are avoidable escalations; deflecting `{reduction_pct}%` directly removes **`-{sim['direct_open_saved']:.1f}` open tickets** (`{sim['current_open_total']} → {sim['direct_open_after']:.1f}`, **`-{sim['direct_open_reduction_pct']:.2f}%`**).
            4. **Active Engineering + L1 Triage Hours Reclaimed (Explicit Assumption):**
               Avoidable tickets average **`{sim['avg_handoffs_per_avoidable']:.2f}` handoffs** each. At **`{sim['eng_active_hrs_per_handoff']:.2f} hrs`** active triage/context-switching per handoff, deflecting `{reduction_pct}%` saves **`{sim['eng_active_hrs_saved_qtr']:.1f}` person-hours/quarter** (`{sim['eng_active_hrs_saved_mo']:.1f}` hrs/mo) at **$0 new hiring cost**.
            """
        )


# ---------------------------------------------------------------------------
# Route active tab
# ---------------------------------------------------------------------------
if st.session_state["active_tab"] == TAB_QUEUE:
    render_tab_open_queue()
elif st.session_state["active_tab"] == TAB_GATEKEEPER:
    render_tab_gatekeeper()
else:
    render_tab_ops_pulse()
