"""Dynamic metric computation for RideOps Triage & Escalation Gatekeeper.

ZERO hardcoded statistics: every KPI, queue score, chart series, and What-If
simulator baseline is computed directly from rideops_support_tickets.csv.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


AVOIDABLE_OUTCOMES: set[str] = {
    "Insufficient info - returned to L1",
    "Config issue - returned to L1",
    "Duplicate of known issue",
    "Not a bug - how-to",
    "Not reproducible",
}

PRIORITY_WEIGHTS: dict[str, float] = {"P1": 40.0, "P2": 28.0, "P3": 15.0, "P4": 5.0}
TIER_WEIGHTS: dict[str, float] = {"Enterprise": 25.0, "Mid-market": 15.0, "SMB": 8.0}

MONTH_END_CUTOFFS: list[tuple[str, str, str]] = [
    ("2026-07", "Jul 2026", "2026-07-31 23:59:59"),
    ("2026-08", "Aug 2026", "2026-08-31 23:59:59"),
    ("2026-09", "Sep 2026", "2026-09-30 23:59:59"),
]


def load_tickets(csv_path: str | Path) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Load rideops_support_tickets.csv and derive clean analytical fields.

    Returns (df, data_pull_ts) where data_pull_ts defaults to 2026-09-30 23:59:59
    (end of the 30 Sep 2026 data pull day).
    """
    df = pd.read_csv(csv_path)

    for col in ["created_at", "first_response_at", "first_closed_at", "final_closed_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["eng_handoffs"] = pd.to_numeric(df["eng_handoffs"], errors="coerce").fillna(0).astype(int)
    df["reopen_count"] = pd.to_numeric(df["reopen_count"], errors="coerce").fillna(0).astype(int)
    df["csat_score"] = pd.to_numeric(df["csat_score"], errors="coerce")
    df["eng_outcome"] = df["eng_outcome"].fillna("").astype(str).str.strip()
    df["eng_ticket_id"] = df["eng_ticket_id"].fillna("").astype(str).str.strip()
    df["description"] = df["description"].fillna("").astype(str).str.strip()

    # Reference data pull timestamp: exact end of 30 Sep 2026 IST (matches analysis/metrics_summary.json)
    max_ts = max(
        ts for ts in [
            df["created_at"].max(),
            df["first_response_at"].max(),
            df["first_closed_at"].max(),
            df["final_closed_at"].max(),
        ]
        if pd.notna(ts)
    )
    data_pull_ts = max(pd.Timestamp("2026-09-30 23:59:59"), max_ts)

    df["is_open"] = df["status"] != "Closed"
    df["is_escalated"] = df["escalated_to_eng"] == "Yes"
    df["is_fixed"] = df["is_escalated"] & (df["eng_outcome"] == "Fixed")
    df["is_avoidable_escalation"] = df["is_escalated"] & df["eng_outcome"].isin(AVOIDABLE_OUTCOMES)
    df["is_reopened"] = df["reopen_count"] > 0

    df["first_response_hrs"] = (df["first_response_at"] - df["created_at"]).dt.total_seconds() / 3600.0
    df["first_close_hrs"] = (df["first_closed_at"] - df["created_at"]).dt.total_seconds() / 3600.0
    df["final_close_hrs"] = (df["final_closed_at"] - df["created_at"]).dt.total_seconds() / 3600.0
    df["age_hrs"] = np.where(
        df["is_open"],
        (data_pull_ts - df["created_at"]).dt.total_seconds() / 3600.0,
        df["final_close_hrs"],
    )

    df["is_ping_pong"] = df["eng_handoffs"] >= 2
    df["is_stale"] = df["is_open"] & (df["age_hrs"] > 48.0)
    df["month_key"] = df["created_at"].dt.strftime("%Y-%m")
    df["month_label"] = df["created_at"].dt.strftime("%b %Y")

    return df, data_pull_ts


def compute_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly ticket volume, escalation split, and EOM open backlog."""
    rows: list[dict[str, Any]] = []
    for month_key, month_label, cutoff_str in MONTH_END_CUTOFFS:
        m_df = df[df["month_key"] == month_key]
        cutoff = pd.Timestamp(cutoff_str)

        # True end-of-month open backlog: created on or before month end, still not finally closed at month end
        open_eom = df[
            (df["created_at"] <= cutoff)
            & (df["final_closed_at"].isna() | (df["final_closed_at"] > cutoff))
        ]
        total = int(len(m_df))
        esc_total = int(m_df["is_escalated"].sum())
        esc_fixed = int(m_df["is_fixed"].sum())
        esc_avoidable = int(m_df["is_avoidable_escalation"].sum())
        non_esc = total - esc_total

        rows.append(
            {
                "month_key": month_key,
                "month_label": month_label,
                "total_tickets": total,
                "non_escalated": non_esc,
                "escalated_total": esc_total,
                "escalated_fixed": esc_fixed,
                "escalated_avoidable": esc_avoidable,
                "escalation_rate_pct": round((esc_total / total) * 100.0, 1) if total else 0.0,
                "avoidable_of_esc_pct": round((esc_avoidable / esc_total) * 100.0, 1) if esc_total else 0.0,
                "open_eom_total": int(len(open_eom)),
                "open_eom_escalated": int(open_eom["is_escalated"].sum()),
                "open_eom_avoidable": int(open_eom["is_avoidable_escalation"].sum()),
            }
        )
    return pd.DataFrame(rows)


def compute_headline_kpis(df: pd.DataFrame) -> dict[str, Any]:
    """Compute all headline KPIs dynamically from rideops_support_tickets.csv."""
    total_tickets = int(len(df))
    open_df = df[df["is_open"]]
    closed_df = df[~df["is_open"]]
    first_closed_df = df[df["first_closed_at"].notna()]
    esc_df = df[df["is_escalated"]]
    non_esc_closed = closed_df[~closed_df["is_escalated"]]
    esc_closed = closed_df[closed_df["is_escalated"]]
    avoid_closed = closed_df[closed_df["is_avoidable_escalation"]]

    open_total = int(len(open_df))
    open_l1 = int((open_df["status"] == "Open - with L1").sum())
    open_eng = int((open_df["status"] == "Open - with Engineering").sum())
    open_escalated = int(open_df["is_escalated"].sum())
    open_avoidable = int(open_df["is_avoidable_escalation"].sum())
    open_ping_pong = int(open_df["is_ping_pong"].sum())
    open_stale = int(open_df["is_stale"].sum())

    esc_total = int(len(esc_df))
    fixed_total = int(esc_df["is_fixed"].sum())
    avoidable_total = int(esc_df["is_avoidable_escalation"].sum())

    esc_rate_pct = (esc_total / total_tickets * 100.0) if total_tickets else 0.0
    avoidable_rate_pct = (avoidable_total / esc_total * 100.0) if esc_total else 0.0
    fixed_rate_pct = (fixed_total / esc_total * 100.0) if esc_total else 0.0

    # Reopen rate: primary = all tickets (matches analysis/metrics_summary.json), secondary = closed tickets
    reopened_total = int(df["is_reopened"].sum())
    reopened_closed = int(closed_df["is_reopened"].sum())
    reopen_rate_all_pct = (reopened_total / total_tickets * 100.0) if total_tickets else 0.0
    reopen_rate_closed_pct = (reopened_closed / len(closed_df) * 100.0) if len(closed_df) else 0.0

    # True First-Contact Resolution (FCR): Closed by L1 without escalation and without reopen
    true_fcr_count = int(((~df["is_open"]) & (~df["is_escalated"]) & (~df["is_reopened"])).sum())
    true_fcr_closed_pct = (true_fcr_count / len(closed_df) * 100.0) if len(closed_df) else 0.0
    true_fcr_all_pct = (true_fcr_count / total_tickets * 100.0) if total_tickets else 0.0

    med_non_esc_hrs = float(non_esc_closed["final_close_hrs"].median()) if len(non_esc_closed) else 0.0
    mean_non_esc_hrs = float(non_esc_closed["final_close_hrs"].mean()) if len(non_esc_closed) else 0.0
    med_esc_hrs = float(esc_closed["final_close_hrs"].median()) if len(esc_closed) else 0.0
    mean_esc_hrs = float(esc_closed["final_close_hrs"].mean()) if len(esc_closed) else 0.0
    med_avoid_hrs = float(avoid_closed["final_close_hrs"].median()) if len(avoid_closed) else 0.0
    mean_avoid_hrs = float(avoid_closed["final_close_hrs"].mean()) if len(avoid_closed) else 0.0
    esc_penalty_multiple = (med_esc_hrs / med_non_esc_hrs) if med_non_esc_hrs > 0 else 0.0

    monthly = compute_monthly_summary(df)
    jul_row = monthly[monthly["month_key"] == "2026-07"].iloc[0]
    sep_row = monthly[monthly["month_key"] == "2026-09"].iloc[0]
    vol_growth_pct = (
        (sep_row["total_tickets"] - jul_row["total_tickets"]) / jul_row["total_tickets"] * 100.0
        if jul_row["total_tickets"]
        else 0.0
    )
    backlog_growth_pct = (
        (sep_row["open_eom_total"] - jul_row["open_eom_total"]) / jul_row["open_eom_total"] * 100.0
        if jul_row["open_eom_total"]
        else 0.0
    )

    return {
        "total_tickets": total_tickets,
        "closed_total": int(len(closed_df)),
        "open_total": open_total,
        "open_l1": open_l1,
        "open_eng": open_eng,
        "open_escalated": open_escalated,
        "open_avoidable": open_avoidable,
        "open_ping_pong": open_ping_pong,
        "open_stale": open_stale,
        "escalated_total": esc_total,
        "escalation_rate_pct": round(esc_rate_pct, 1),
        "fixed_total": fixed_total,
        "fixed_rate_pct": round(fixed_rate_pct, 1),
        "avoidable_total": avoidable_total,
        "avoidable_rate_pct": round(avoidable_rate_pct, 1),
        "reopened_total": reopened_total,
        "reopened_closed": reopened_closed,
        "reopen_rate_all_pct": round(reopen_rate_all_pct, 2),
        "reopen_rate_closed_pct": round(reopen_rate_closed_pct, 2),
        "true_fcr_count": true_fcr_count,
        "true_fcr_closed_pct": round(true_fcr_closed_pct, 2),
        "true_fcr_all_pct": round(true_fcr_all_pct, 2),
        "median_non_esc_hrs": round(med_non_esc_hrs, 2),
        "mean_non_esc_hrs": round(mean_non_esc_hrs, 2),
        "median_esc_hrs": round(med_esc_hrs, 2),
        "mean_esc_hrs": round(mean_esc_hrs, 2),
        "median_avoidable_hrs": round(med_avoid_hrs, 2),
        "mean_avoidable_hrs": round(mean_avoid_hrs, 2),
        "esc_penalty_multiple": round(esc_penalty_multiple, 2),
        "mean_csat": round(float(df["csat_score"].mean()), 2) if df["csat_score"].notna().any() else 0.0,
        "jul_tickets": int(jul_row["total_tickets"]),
        "sep_tickets": int(sep_row["total_tickets"]),
        "vol_growth_jul_sep_pct": round(vol_growth_pct, 2),
        "open_eom_jul": int(jul_row["open_eom_total"]),
        "open_eom_sep": int(sep_row["open_eom_total"]),
        "backlog_growth_jul_sep_pct": round(backlog_growth_pct, 2),
    }


def build_open_queue(df: pd.DataFrame) -> pd.DataFrame:
    """Rank all open tickets by composite Urgency Score (0-100).

    Formula:
      Priority weight (P1=40, P2=28, P3=15, P4=5)
      + Client Tier weight (Enterprise=25, Mid-market=15, SMB=8)
      + Age score (min(age_hrs / 24 * 3.0, 20.0))
      + Handoff Ping-Pong score (min(eng_handoffs * 5.0, 15.0))
      + Reopen bonus (+5 if reopen_count > 0), capped at 100.
    """
    q = df[df["is_open"]].copy()
    if q.empty:
        return q

    p_score = q["priority"].map(PRIORITY_WEIGHTS).fillna(5.0)
    t_score = q["client_tier"].map(TIER_WEIGHTS).fillna(8.0)
    age_score = np.minimum((q["age_hrs"].clip(lower=0.0) / 24.0) * 3.0, 20.0)
    ho_score = np.minimum(q["eng_handoffs"] * 5.0, 15.0)
    reopen_bonus = np.where(q["is_reopened"], 5.0, 0.0)

    q["urgency_score"] = np.minimum(100.0, p_score + t_score + age_score + ho_score + reopen_bonus).round(1)
    q["age_days"] = (q["age_hrs"] / 24.0).round(1)
    q["age_label"] = q["age_hrs"].apply(
        lambda h: f"{h / 24.0:.1f}d ({h:.0f}h)" if h >= 24.0 else f"{h:.1f}h"
    )

    def _risk_badge(row: pd.Series) -> str:
        flags: list[str] = []
        if row["is_ping_pong"]:
            flags.append("Ping-Pong Risk")
        if row["is_stale"]:
            flags.append("Stale >48h")
        if row["is_reopened"]:
            flags.append("Reopened")
        return " | ".join(flags) if flags else "Normal"

    q["risk_badges"] = q.apply(_risk_badge, axis=1)
    q = q.sort_values(
        by=["urgency_score", "age_hrs", "eng_handoffs"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    return q


def compute_escalation_waste(df: pd.DataFrame) -> pd.DataFrame:
    """Breakdown of every eng_outcome among escalated tickets (Fixed vs Avoidable)."""
    esc = df[df["is_escalated"]].copy()
    total_esc = len(esc)
    if total_esc == 0:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for outcome, grp in esc.groupby("eng_outcome", dropna=False):
        label = outcome if outcome else "Pending / Blank"
        closed_grp = grp[~grp["is_open"]]
        cnt = int(len(grp))
        rows.append(
            {
                "eng_outcome": label,
                "count": cnt,
                "share_pct": round(cnt / total_esc * 100.0, 1),
                "bucket": "Fixed (Valid Bug)" if label == "Fixed" else "Avoidable Escalation",
                "is_avoidable": label in AVOIDABLE_OUTCOMES,
                "median_close_hrs": round(float(closed_grp["final_close_hrs"].median()), 1)
                if len(closed_grp)
                else np.nan,
                "open_count": int(grp["is_open"].sum()),
            }
        )
    out = pd.DataFrame(rows)
    # Sort Avoidable outcomes descending, with Fixed at top or bottom cleanly separated
    out = out.sort_values(by=["is_avoidable", "count"], ascending=[False, False]).reset_index(drop=True)
    return out


def compute_handoff_penalty(df: pd.DataFrame) -> pd.DataFrame:
    """Resolution hours across Non-Escalated (0) vs 1, 2, 3+ engineering handoffs."""
    closed = df[~df["is_open"]].copy()
    closed["handoff_bucket"] = np.where(
        closed["eng_handoffs"] >= 3,
        "3+ Handoffs",
        closed["eng_handoffs"].map(
            {0: "0 (L1 Resolved)", 1: "1 Handoff", 2: "2 Handoffs"}
        ),
    )
    order = ["0 (L1 Resolved)", "1 Handoff", "2 Handoffs", "3+ Handoffs"]
    base_df = closed[closed["handoff_bucket"] == "0 (L1 Resolved)"]
    base_med = float(base_df["final_close_hrs"].median()) if len(base_df) else 1.0

    rows: list[dict[str, Any]] = []
    for bucket in order:
        grp = closed[closed["handoff_bucket"] == bucket]
        if grp.empty:
            continue
        med_h = float(grp["final_close_hrs"].median())
        mean_h = float(grp["final_close_hrs"].mean())
        rows.append(
            {
                "handoff_bucket": bucket,
                "closed_tickets": int(len(grp)),
                "median_hrs": round(med_h, 1),
                "mean_hrs": round(mean_h, 1),
                "multiple_vs_l1": round(med_h / base_med, 1) if base_med > 0 else 1.0,
            }
        )
    return pd.DataFrame(rows)


def compute_agent_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Compute agent-level speed, quality, escalation, and CSAT metrics."""
    rows: list[dict[str, Any]] = []
    for agent, grp in df.groupby("assigned_agent"):
        n = int(len(grp))
        esc_grp = grp[grp["is_escalated"]]
        esc_n = int(len(esc_grp))
        avoid_n = int(grp["is_avoidable_escalation"].sum())
        how_to_n = int((grp["eng_outcome"] == "Not a bug - how-to").sum())
        fc_grp = grp[grp["first_closed_at"].notna()]
        closed_grp = grp[~grp["is_open"]]
        reopen_n = int(grp["is_reopened"].sum())
        reopen_closed_n = int(closed_grp["is_reopened"].sum())
        open_n = int(grp["is_open"].sum())

        reopen_rate_all = (reopen_n / n * 100.0) if n else 0.0
        reopen_rate_closed = (reopen_closed_n / len(closed_grp) * 100.0) if len(closed_grp) else 0.0
        esc_rate = (esc_n / n * 100.0) if n else 0.0
        avoid_of_esc = (avoid_n / esc_n * 100.0) if esc_n else 0.0
        med_fc = float(fc_grp["first_close_hrs"].median()) if len(fc_grp) else 0.0
        med_final = float(closed_grp["final_close_hrs"].median()) if len(closed_grp) else 0.0
        mean_csat = float(grp["csat_score"].mean()) if grp["csat_score"].notna().any() else np.nan
        true_fcr_n = int(((~grp["is_open"]) & (~grp["is_escalated"]) & (~grp["is_reopened"])).sum())
        true_fcr_closed = (true_fcr_n / len(closed_grp) * 100.0) if len(closed_grp) else 0.0

        rows.append(
            {
                "assigned_agent": agent,
                "total_tickets": n,
                "open_tickets": open_n,
                "escalated_count": esc_n,
                "escalation_rate_pct": round(esc_rate, 2),
                "avoidable_esc_count": avoid_n,
                "avoidable_of_esc_pct": round(avoid_of_esc, 2),
                "how_to_esc_count": how_to_n,
                "median_first_close_hrs": round(med_fc, 2),
                "median_final_close_hrs": round(med_final, 2),
                "reopened_tickets": reopen_n,
                "reopen_rate_pct": round(reopen_rate_all, 2),
                "reopen_rate_closed_pct": round(reopen_rate_closed, 2),
                "true_fcr_closed_pct": round(true_fcr_closed, 2),
                "mean_csat": round(mean_csat, 2) if pd.notna(mean_csat) else np.nan,
            }
        )

    res = pd.DataFrame(rows)
    if res.empty:
        return res

    # Dynamic coaching profile labels based on team medians / 8% reopen guardrail
    med_speed = float(res["median_first_close_hrs"].median())
    med_esc = float(res["escalation_rate_pct"].median())

    def _profile(row: pd.Series) -> str:
        if row["reopen_rate_pct"] >= 15.0:
            return "Premature Closure Risk"
        if row["escalation_rate_pct"] >= med_esc + 15.0:
            return "Over-Escalation Risk"
        if row["reopen_rate_pct"] < 8.0 and row["escalation_rate_pct"] <= med_esc + 5.0:
            return "Benchmark Performer"
        if row["median_first_close_hrs"] <= med_speed and row["reopen_rate_pct"] < 10.0:
            return "Balanced"
        return "Watch / Coach"

    res["coaching_flag"] = res.apply(_profile, axis=1)
    return res.sort_values(by="total_tickets", ascending=False).reset_index(drop=True)


def compute_category_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Category concentration, open backlog, escalation rate, and avoidable rate."""
    total_all = len(df)
    rows: list[dict[str, Any]] = []
    for cat, grp in df.groupby("category"):
        n = int(len(grp))
        esc_n = int(grp["is_escalated"].sum())
        avoid_n = int(grp["is_avoidable_escalation"].sum())
        dup_n = int((grp["eng_outcome"] == "Duplicate of known issue").sum())
        open_n = int(grp["is_open"].sum())
        rows.append(
            {
                "category": cat,
                "total_tickets": n,
                "share_pct": round(n / total_all * 100.0, 1) if total_all else 0.0,
                "open_tickets": open_n,
                "escalated_count": esc_n,
                "escalation_rate_pct": round(esc_n / n * 100.0, 1) if n else 0.0,
                "avoidable_count": avoid_n,
                "avoidable_of_esc_pct": round(avoid_n / esc_n * 100.0, 1) if esc_n else 0.0,
                "duplicate_count": dup_n,
            }
        )
    return pd.DataFrame(rows).sort_values(by="total_tickets", ascending=False).reset_index(drop=True)


def compute_what_if_simulation(
    df: pd.DataFrame,
    reduction_pct: float,
    reopen_reduction_pct: float = 0.0,
    eng_active_hrs_per_handoff: float = 1.5,
) -> dict[str, Any]:
    """Simulate impact of cutting avoidable escalations (and optionally premature reopens)
    at $0 hiring cost. Exact formulas align with analysis/metrics_summary.json `what_if_baseline`:
      - Excess elapsed hours/avoidable ticket = mean_final_close(avoidable_closed) - mean_final_close(non_esc_closed)
      - Reopen extra hours/reopened ticket = mean(final_close - first_close) on closed reopened tickets
      - Direct snapshot open backlog reduction = sep_open_avoidable * deflection_frac
      - Little's Law steady-state open backlog reduction =
          sep_arrival_rate_per_hour * (
              (sep_avoidable / sep_tickets) * deflection_frac * excess_hours_per_avoidable
              + (sep_reopened / sep_tickets) * reopen_red_frac * mean_reopen_extra_hours
          )
    """
    frac = max(0.0, min(1.0, float(reduction_pct) / 100.0))
    reopen_frac = max(0.0, min(1.0, float(reopen_reduction_pct) / 100.0))

    total_tickets_qtr = int(len(df))
    esc_df = df[df["is_escalated"]]
    avoid_df = df[df["is_avoidable_escalation"]]
    open_df = df[df["is_open"]]
    closed_df = df[~df["is_open"]]
    non_esc_closed = closed_df[~closed_df["is_escalated"]]
    avoid_closed = closed_df[closed_df["is_avoidable_escalation"]]
    reopened_closed = closed_df[closed_df["is_reopened"] & closed_df["first_closed_at"].notna()]

    sep_df = df[df["month_key"] == "2026-09"]
    sep_tickets = int(len(sep_df))
    sep_avoidable = int(sep_df["is_avoidable_escalation"].sum())
    sep_reopened = int(sep_df["is_reopened"].sum())
    sep_arrival_rate_per_hour = sep_tickets / (30.0 * 24.0) if sep_tickets else 0.0

    total_avoidable_qtr = int(len(avoid_df))
    total_esc_qtr = int(len(esc_df))
    total_reopened_qtr = int(df["is_reopened"].sum())
    current_open_total = int(len(open_df))
    current_open_avoidable = int(open_df["is_avoidable_escalation"].sum())

    med_l1_hrs = float(non_esc_closed["final_close_hrs"].median()) if len(non_esc_closed) else 0.0
    mean_l1_hrs = float(non_esc_closed["final_close_hrs"].mean()) if len(non_esc_closed) else 0.0
    med_avoid_hrs = float(avoid_closed["final_close_hrs"].median()) if len(avoid_closed) else 1.0
    mean_avoid_hrs = float(avoid_closed["final_close_hrs"].mean()) if len(avoid_closed) else 1.0
    excess_hrs_per_avoidable = max(0.0, mean_avoid_hrs - mean_l1_hrs)

    reopen_extra_hrs = (
        float((reopened_closed["final_close_hrs"] - reopened_closed["first_close_hrs"]).mean())
        if len(reopened_closed)
        else 0.0
    )

    avg_handoffs_per_avoidable = float(avoid_df["eng_handoffs"].mean()) if len(avoid_df) else 0.0
    total_avoidable_handoffs_qtr = int(avoid_df["eng_handoffs"].sum())

    # Deflected engineering tickets
    deflected_qtr = round(total_avoidable_qtr * frac, 1)
    deflected_sep_mo = round(sep_avoidable * frac, 1)

    # Elapsed cycle-time hours reclaimed (exact match to analyst what_if_baseline)
    elapsed_hrs_saved_avoid_qtr = round(total_avoidable_qtr * frac * excess_hrs_per_avoidable, 1)
    elapsed_hrs_saved_avoid_sep = round(sep_avoidable * frac * excess_hrs_per_avoidable, 1)
    elapsed_hrs_saved_reopen_qtr = round(total_reopened_qtr * reopen_frac * reopen_extra_hrs, 1)
    elapsed_hrs_saved_reopen_sep = round(sep_reopened * reopen_frac * reopen_extra_hrs, 1)
    elapsed_hrs_saved_total_qtr = round(elapsed_hrs_saved_avoid_qtr + elapsed_hrs_saved_reopen_qtr, 1)
    elapsed_hrs_saved_total_sep = round(elapsed_hrs_saved_avoid_sep + elapsed_hrs_saved_reopen_sep, 1)

    # Active Engineering + L1 triage handling hours saved (explicitly parameterized assumption)
    eng_active_hrs_saved_qtr = round(total_avoidable_handoffs_qtr * frac * eng_active_hrs_per_handoff, 1)
    eng_active_hrs_saved_mo = round(eng_active_hrs_saved_qtr / 3.0, 1)

    # Backlog reduction — both Direct Snapshot (on the 22 open avoidable tickets) & Little's Law Steady-State
    direct_open_saved = round(current_open_avoidable * frac, 1)
    direct_open_after = round(max(0.0, current_open_total - direct_open_saved), 1)
    direct_open_reduction_pct = (
        round((direct_open_saved / current_open_total) * 100.0, 2) if current_open_total else 0.0
    )

    delta_w = (
        ((sep_avoidable / sep_tickets) * frac * excess_hrs_per_avoidable)
        + ((sep_reopened / sep_tickets) * reopen_frac * reopen_extra_hrs)
        if sep_tickets
        else 0.0
    )
    littles_law_saved = round(sep_arrival_rate_per_hour * delta_w, 1)
    littles_law_after = round(max(0.0, current_open_total - littles_law_saved), 1)
    littles_law_reduction_pct = (
        round((sep_arrival_rate_per_hour * delta_w / current_open_total) * 100.0, 2)
        if current_open_total
        else 0.0
    )

    new_esc_total = max(0.0, total_esc_qtr - (total_avoidable_qtr * frac))
    new_avoidable_total = max(0.0, total_avoidable_qtr * (1.0 - frac))
    new_esc_rate_pct = round((new_esc_total / total_tickets_qtr) * 100.0, 2) if total_tickets_qtr else 0.0
    new_avoidable_rate_pct = (
        round((new_avoidable_total / new_esc_total) * 100.0, 2) if new_esc_total > 0 else 0.0
    )
    current_avoidable_rate_pct = (
        round((total_avoidable_qtr / total_esc_qtr) * 100.0, 2) if total_esc_qtr else 0.0
    )

    return {
        "reduction_pct": reduction_pct,
        "reopen_reduction_pct": reopen_reduction_pct,
        "total_avoidable_qtr": total_avoidable_qtr,
        "sep_tickets": sep_tickets,
        "sep_avoidable": sep_avoidable,
        "sep_reopened": sep_reopened,
        "sep_arrival_rate_per_hour": round(sep_arrival_rate_per_hour, 4),
        "deflected_qtr": deflected_qtr,
        "deflected_sep_mo": deflected_sep_mo,
        "avg_handoffs_per_avoidable": round(avg_handoffs_per_avoidable, 2),
        "excess_hrs_per_avoidable": round(excess_hrs_per_avoidable, 2),
        "reopen_extra_hrs": round(reopen_extra_hrs, 2),
        "elapsed_hrs_saved_avoid_qtr": elapsed_hrs_saved_avoid_qtr,
        "elapsed_hrs_saved_avoid_sep": elapsed_hrs_saved_avoid_sep,
        "elapsed_hrs_saved_reopen_qtr": elapsed_hrs_saved_reopen_qtr,
        "elapsed_hrs_saved_reopen_sep": elapsed_hrs_saved_reopen_sep,
        "elapsed_hrs_saved_total_qtr": elapsed_hrs_saved_total_qtr,
        "elapsed_hrs_saved_total_sep": elapsed_hrs_saved_total_sep,
        "avg_resolution_delta_w": round(delta_w, 2),
        "eng_active_hrs_per_handoff": eng_active_hrs_per_handoff,
        "eng_active_hrs_saved_qtr": eng_active_hrs_saved_qtr,
        "eng_active_hrs_saved_mo": eng_active_hrs_saved_mo,
        "current_open_total": current_open_total,
        "current_open_avoidable": current_open_avoidable,
        "direct_open_saved": direct_open_saved,
        "direct_open_after": direct_open_after,
        "direct_open_reduction_pct": direct_open_reduction_pct,
        "littles_law_saved": littles_law_saved,
        "littles_law_after": littles_law_after,
        "littles_law_reduction_pct": littles_law_reduction_pct,
        "current_avoidable_rate_pct": current_avoidable_rate_pct,
        "new_avoidable_rate_pct": new_avoidable_rate_pct,
        "new_esc_rate_pct": new_esc_rate_pct,
        "median_l1_hrs": round(med_l1_hrs, 2),
        "median_avoidable_hrs": round(med_avoid_hrs, 2),
    }
