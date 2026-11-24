#!/usr/bin/env python3
"""
RideOps Support Case Study — Programmatic Data Diagnosis Script
================================================================
Computes every diagnostic metric directly from rideops_support_tickets.csv
(zero hardcoded statistics) and saves a structured JSON report to
analysis/metrics_summary.json while printing an executive summary to stdout.

Uses Python standard library only so it runs cleanly in any Python 3.9+ env.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_DIR / "rideops_support_tickets.csv"
OUTPUT_JSON = Path(__file__).resolve().parent / "metrics_summary.json"

# Canonical data pull timestamp from 1.pdf & rideops_data_dictionary.csv ("30 Sep 2026")
DATA_PULL_ISO = "2026-09-30 23:59:59"
DATA_PULL_DT = datetime.strptime(DATA_PULL_ISO, "%Y-%m-%d %H:%M:%S")

AVOIDABLE_OUTCOMES = {
    "Insufficient info - returned to L1",
    "Config issue - returned to L1",
    "Duplicate of known issue",
    "Not a bug - how-to",
    "Not reproducible",
}

ALL_OUTCOME_ORDER = [
    "Fixed",
    "Insufficient info - returned to L1",
    "Config issue - returned to L1",
    "Duplicate of known issue",
    "Not a bug - how-to",
    "Not reproducible",
]


def parse_dt(value: str) -> datetime | None:
    s = (value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized datetime format: {value!r}")


def hours_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds() / 3600.0


def safe_pct(num: int | float, den: int | float, decimals: int = 2) -> float | None:
    if not den:
        return None
    return round((num / den) * 100.0, decimals)


def safe_mean(vals: list[float], decimals: int = 2) -> float | None:
    if not vals:
        return None
    return round(statistics.mean(vals), decimals)


def safe_median(vals: list[float], decimals: int = 2) -> float | None:
    if not vals:
        return None
    return round(statistics.median(vals), decimals)


def safe_ratio(num: float | None, den: float | None, decimals: int = 2) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return round(num / den, decimals)


def normalize_description(desc: str) -> str:
    s = re.sub(r"\b\d+\b", "<N>", desc.strip())
    s = re.sub(r"\b(night|morning|evening|afternoon|general)\s+shift\b", "<SHIFT>", s, flags=re.IGNORECASE)
    s = re.sub(r"<N>\s*(AM|PM)\s+shift", "<SHIFT>", s, flags=re.IGNORECASE)
    return s


def load_tickets(csv_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            created_dt = parse_dt(raw["created_at"])
            first_resp_dt = parse_dt(raw["first_response_at"])
            first_closed_dt = parse_dt(raw["first_closed_at"])
            final_closed_dt = parse_dt(raw["final_closed_at"])
            escalated = raw["escalated_to_eng"].strip() == "Yes"
            outcome = raw["eng_outcome"].strip()
            status = raw["status"].strip()
            is_open = status != "Closed"
            reopen_count = int(raw["reopen_count"])
            eng_handoffs = int(raw["eng_handoffs"])
            csat_raw = raw["csat_score"].strip()
            csat = int(csat_raw) if csat_raw else None

            rec = {
                "ticket_id": raw["ticket_id"].strip(),
                "created_at": raw["created_at"].strip(),
                "created_dt": created_dt,
                "created_month": raw["created_at"].strip()[:7],
                "channel": raw["channel"].strip(),
                "client_id": raw["client_id"].strip(),
                "client_name": raw["client_name"].strip(),
                "client_tier": raw["client_tier"].strip(),
                "category": raw["category"].strip(),
                "priority": raw["priority"].strip(),
                "description": raw["description"].strip(),
                "normalized_description": normalize_description(raw["description"]),
                "assigned_agent": raw["assigned_agent"].strip(),
                "first_response_at": raw["first_response_at"].strip(),
                "first_resp_dt": first_resp_dt,
                "escalated": escalated,
                "eng_ticket_id": raw["eng_ticket_id"].strip(),
                "eng_handoffs": eng_handoffs,
                "eng_outcome": outcome,
                "is_avoidable_escalation": escalated and (outcome in AVOIDABLE_OUTCOMES),
                "is_fixed_escalation": escalated and (outcome == "Fixed"),
                "status": status,
                "is_open": is_open,
                "first_closed_at": raw["first_closed_at"].strip(),
                "first_closed_dt": first_closed_dt,
                "final_closed_at": raw["final_closed_at"].strip(),
                "final_closed_dt": final_closed_dt,
                "reopen_count": reopen_count,
                "is_reopened": reopen_count > 0,
                "csat": csat,
                "first_response_hours": hours_between(created_dt, first_resp_dt),
                "first_close_hours": hours_between(created_dt, first_closed_dt),
                "final_close_hours": hours_between(created_dt, final_closed_dt),
                "reopen_extra_hours": hours_between(first_closed_dt, final_closed_dt),
                "open_age_hours": hours_between(created_dt, DATA_PULL_DT) if is_open else None,
            }
            records.append(rec)
    return records


def summarize_group(sub: list[dict[str, Any]], total_tickets: int, total_open: int, total_esc: int, total_avoid: int) -> dict[str, Any]:
    n = len(sub)
    closed = [r for r in sub if not r["is_open"]]
    open_rows = [r for r in sub if r["is_open"]]
    open_l1 = [r for r in open_rows if r["status"] == "Open - with L1"]
    open_eng = [r for r in open_rows if r["status"] == "Open - with Engineering"]
    esc = [r for r in sub if r["escalated"]]
    avoid = [r for r in esc if r["is_avoidable_escalation"]]
    fixed = [r for r in esc if r["is_fixed_escalation"]]
    reop_all = [r for r in sub if r["is_reopened"]]
    reop_closed = [r for r in closed if r["is_reopened"]]
    true_fcr = [r for r in closed if (not r["escalated"]) and (not r["is_reopened"])]

    fr_vals = [r["first_response_hours"] for r in sub if r["first_response_hours"] is not None]
    fc_all_vals = [r["first_close_hours"] for r in sub if r["first_close_hours"] is not None]
    fc_closed_vals = [r["first_close_hours"] for r in closed if r["first_close_hours"] is not None]
    fin_vals = [r["final_close_hours"] for r in closed if r["final_close_hours"] is not None]
    csat_vals = [float(r["csat"]) for r in sub if r["csat"] is not None]

    return {
        "tickets": n,
        "share_of_total_pct": safe_pct(n, total_tickets),
        "closed_tickets": len(closed),
        "open_tickets": len(open_rows),
        "open_with_l1": len(open_l1),
        "open_with_eng": len(open_eng),
        "share_of_open_pct": safe_pct(len(open_rows), total_open),
        "escalated_tickets": len(esc),
        "escalation_rate_pct": safe_pct(len(esc), n),
        "share_of_all_escalations_pct": safe_pct(len(esc), total_esc),
        "fixed_escalations": len(fixed),
        "avoidable_escalations": len(avoid),
        "avoidable_share_of_group_escalations_pct": safe_pct(len(avoid), len(esc)),
        "avoidable_rate_of_group_tickets_pct": safe_pct(len(avoid), n),
        "share_of_all_avoidable_escalations_pct": safe_pct(len(avoid), total_avoid),
        "reopened_all_tickets": len(reop_all),
        "reopen_rate_all_pct": safe_pct(len(reop_all), n),
        "reopened_closed_tickets": len(reop_closed),
        "reopen_rate_closed_pct": safe_pct(len(reop_closed), len(closed)),
        "true_fcr_tickets": len(true_fcr),
        "true_fcr_rate_closed_pct": safe_pct(len(true_fcr), len(closed)),
        "true_fcr_rate_all_pct": safe_pct(len(true_fcr), n),
        "first_response_hours_median": safe_median(fr_vals),
        "first_response_hours_mean": safe_mean(fr_vals),
        "first_close_hours_median_all_with_fc": safe_median(fc_all_vals),
        "first_close_hours_mean_all_with_fc": safe_mean(fc_all_vals),
        "first_close_hours_median_closed": safe_median(fc_closed_vals),
        "first_close_hours_mean_closed": safe_mean(fc_closed_vals),
        "final_close_hours_median": safe_median(fin_vals),
        "final_close_hours_mean": safe_mean(fin_vals),
        "csat_mean": safe_mean(csat_vals),
        "csat_responses": len(csat_vals),
    }


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    closed = [r for r in rows if not r["is_open"]]
    open_rows = [r for r in rows if r["is_open"]]
    open_l1 = [r for r in open_rows if r["status"] == "Open - with L1"]
    open_eng = [r for r in open_rows if r["status"] == "Open - with Engineering"]
    esc_rows = [r for r in rows if r["escalated"]]
    non_esc_rows = [r for r in rows if not r["escalated"]]
    avoid_rows = [r for r in esc_rows if r["is_avoidable_escalation"]]
    fixed_rows = [r for r in esc_rows if r["is_fixed_escalation"]]
    closed_esc = [r for r in esc_rows if not r["is_open"]]
    open_esc = [r for r in esc_rows if r["is_open"]]
    closed_avoid = [r for r in closed_esc if r["is_avoidable_escalation"]]
    open_avoid = [r for r in open_esc if r["is_avoidable_escalation"]]
    reop_all = [r for r in rows if r["is_reopened"]]
    reop_closed = [r for r in closed if r["is_reopened"]]
    with_fc = [r for r in rows if r["first_closed_dt"] is not None]
    reop_with_fc = [r for r in with_fc if r["is_reopened"]]
    true_fcr = [r for r in closed if (not r["escalated"]) and (not r["is_reopened"])]

    # 1. Overview & data quality notes
    open_reopened_with_fc = [r["ticket_id"] for r in open_rows if r["first_closed_dt"] is not None]
    open_reopened_without_fc = [r["ticket_id"] for r in open_rows if r["is_reopened"] and r["first_closed_dt"] is None]
    open_without_fr = [r["ticket_id"] for r in open_rows if r["first_resp_dt"] is None]
    eng_ticket_ids = [r["eng_ticket_id"] for r in esc_rows if r["eng_ticket_id"]]

    overview = {
        "total_tickets": total,
        "closed_tickets": len(closed),
        "open_tickets": len(open_rows),
        "open_rate_pct": safe_pct(len(open_rows), total),
        "open_with_l1": len(open_l1),
        "open_with_engineering": len(open_eng),
        "open_escalated_tickets": len(open_esc),
        "open_escalated_share_pct": safe_pct(len(open_esc), len(open_rows)),
        "open_avoidable_escalated_tickets": len(open_avoid),
        "open_avoidable_share_of_open_pct": safe_pct(len(open_avoid), len(open_rows)),
        "date_range": {
            "created_at_min": min(r["created_at"] for r in rows),
            "created_at_max": max(r["created_at"] for r in rows),
            "data_pull_reference_ist": DATA_PULL_ISO,
        },
        "unique_clients": len({r["client_id"] for r in rows}),
        "unique_agents": len({r["assigned_agent"] for r in rows}),
        "unique_categories": len({r["category"] for r in rows}),
        "escalated_tickets": len(esc_rows),
        "non_escalated_tickets": len(non_esc_rows),
        "escalation_rate_pct": safe_pct(len(esc_rows), total),
        "fixed_escalations_all": len(fixed_rows),
        "avoidable_escalations_all": len(avoid_rows),
        "avoidable_escalation_rate_of_escalated_all_pct": safe_pct(len(avoid_rows), len(esc_rows)),
        "avoidable_escalation_rate_of_escalated_closed_pct": safe_pct(len(closed_avoid), len(closed_esc)),
        "avoidable_escalation_rate_of_all_tickets_pct": safe_pct(len(avoid_rows), total),
        "reopened_tickets_all": len(reop_all),
        "reopen_rate_all_pct": safe_pct(len(reop_all), total),
        "reopened_tickets_closed": len(reop_closed),
        "reopen_rate_closed_pct": safe_pct(len(reop_closed), len(closed)),
        "reopen_rate_with_first_closed_pct": safe_pct(len(reop_with_fc), len(with_fc)),
        "true_fcr_tickets": len(true_fcr),
        "true_fcr_rate_closed_pct": safe_pct(len(true_fcr), len(closed)),
        "true_fcr_rate_all_pct": safe_pct(len(true_fcr), total),
        "csat_mean": safe_mean([float(r["csat"]) for r in rows if r["csat"] is not None]),
        "csat_responses": sum(1 for r in rows if r["csat"] is not None),
        "csat_response_rate_pct": safe_pct(sum(1 for r in rows if r["csat"] is not None), total),
        "data_quality_notes": {
            "escalated_with_blank_eng_outcome": sum(1 for r in esc_rows if not r["eng_outcome"]),
            "escalated_with_blank_eng_ticket_id": sum(1 for r in esc_rows if not r["eng_ticket_id"]),
            "unique_eng_ticket_ids": len(set(eng_ticket_ids)),
            "reused_eng_ticket_ids": sum(1 for _, c in Counter(eng_ticket_ids).items() if c > 1),
            "open_tickets_without_first_response": len(open_without_fr),
            "open_tickets_with_first_closed_at_reopened": len(open_reopened_with_fc),
            "open_tickets_reopened_without_first_closed_at": len(open_reopened_without_fc),
            "open_tickets_reopened_without_first_closed_at_ids": open_reopened_without_fc,
        },
    }

    # 2. Monthly volume & End-of-Month open backlog & Daily open averages
    month_specs = [
        ("2026-07", datetime(2026, 7, 2), datetime(2026, 7, 31), 30),
        ("2026-08", datetime(2026, 8, 1), datetime(2026, 8, 31), 31),
        ("2026-09", datetime(2026, 9, 1), datetime(2026, 9, 30), 30),
    ]
    monthly_rows: list[dict[str, Any]] = []
    seen_clients: set[str] = set()
    for ym, start_d, end_d, observed_days in month_specs:
        sub = [r for r in rows if r["created_month"] == ym]
        sub_closed = [r for r in sub if not r["is_open"]]
        sub_esc = [r for r in sub if r["escalated"]]
        sub_avoid = [r for r in sub_esc if r["is_avoidable_escalation"]]
        sub_dups = [r for r in sub_esc if r["eng_outcome"] == "Duplicate of known issue"]
        sub_reop = [r for r in sub if r["is_reopened"]]
        sub_csat = [float(r["csat"]) for r in sub if r["csat"] is not None]
        sub_fin = [r["final_close_hours"] for r in sub_closed if r["final_close_hours"] is not None]

        # End-of-month open snapshot: created <= EOM and (still open OR final_closed > EOM)
        eom_cutoff = end_d.replace(hour=23, minute=59, second=59)
        eom_open = [
            r
            for r in rows
            if r["created_dt"] <= eom_cutoff
            and (r["final_closed_dt"] is None or r["final_closed_dt"] > eom_cutoff)
        ]
        eom_open_esc = [r for r in eom_open if r["escalated"]]
        eom_open_avoid = [r for r in eom_open_esc if r["is_avoidable_escalation"]]

        # Daily open count across the month
        daily_open: list[int] = []
        cur = start_d
        while cur <= end_d:
            eod = cur.replace(hour=23, minute=59, second=59)
            cnt = sum(
                1
                for r in rows
                if r["created_dt"] <= eod and (r["final_closed_dt"] is None or r["final_closed_dt"] > eod)
            )
            daily_open.append(cnt)
            cur += timedelta(days=1)

        active_clients = {r["client_id"] for r in sub}
        new_clients = active_clients - seen_clients
        seen_clients |= active_clients

        lam_per_hr = len(sub) / (observed_days * 24.0)
        mean_w = statistics.mean(sub_fin) if sub_fin else 0.0

        monthly_rows.append(
            {
                "month": ym,
                "observed_days": observed_days,
                "tickets_created": len(sub),
                "tickets_per_day": round(len(sub) / observed_days, 2),
                "active_clients": len(active_clients),
                "new_clients_first_seen": len(new_clients),
                "tickets_per_active_client": round(len(sub) / len(active_clients), 2),
                "escalated_tickets": len(sub_esc),
                "escalation_rate_pct": safe_pct(len(sub_esc), len(sub)),
                "avoidable_escalations": len(sub_avoid),
                "avoidable_share_of_escalated_pct": safe_pct(len(sub_avoid), len(sub_esc)),
                "duplicate_escalations": len(sub_dups),
                "reopened_tickets": len(sub_reop),
                "reopen_rate_pct": safe_pct(len(sub_reop), len(sub)),
                "final_close_hours_median": safe_median(sub_fin),
                "final_close_hours_mean": safe_mean(sub_fin),
                "csat_mean": safe_mean(sub_csat),
                "eom_date": end_d.strftime("%Y-%m-%d"),
                "eom_open_backlog": len(eom_open),
                "eom_open_escalated": len(eom_open_esc),
                "eom_open_escalated_share_pct": safe_pct(len(eom_open_esc), len(eom_open)),
                "eom_open_avoidable_escalated": len(eom_open_avoid),
                "daily_open_mean": safe_mean([float(x) for x in daily_open]),
                "daily_open_min": min(daily_open),
                "daily_open_max": max(daily_open),
                "littles_law_arrival_rate_per_hour": round(lam_per_hr, 4),
                "littles_law_implied_open_backlog": round(lam_per_hr * mean_w, 2),
            }
        )

    m_jul, m_aug, m_sep = monthly_rows[0], monthly_rows[1], monthly_rows[2]
    monthly_trends = {
        "months": monthly_rows,
        "volume_growth": {
            "jul_to_aug_pct": safe_pct(m_aug["tickets_created"] - m_jul["tickets_created"], m_jul["tickets_created"]),
            "aug_to_sep_pct": safe_pct(m_sep["tickets_created"] - m_aug["tickets_created"], m_aug["tickets_created"]),
            "jul_to_sep_pct": safe_pct(m_sep["tickets_created"] - m_jul["tickets_created"], m_jul["tickets_created"]),
            "jul_to_sep_delta": m_sep["tickets_created"] - m_jul["tickets_created"],
        },
        "eom_open_backlog_growth": {
            "jul_to_aug_pct": safe_pct(m_aug["eom_open_backlog"] - m_jul["eom_open_backlog"], m_jul["eom_open_backlog"]),
            "aug_to_sep_pct": safe_pct(m_sep["eom_open_backlog"] - m_aug["eom_open_backlog"], m_aug["eom_open_backlog"]),
            "jul_to_sep_pct": safe_pct(m_sep["eom_open_backlog"] - m_jul["eom_open_backlog"], m_jul["eom_open_backlog"]),
            "jul_to_sep_delta": m_sep["eom_open_backlog"] - m_jul["eom_open_backlog"],
        },
        "daily_open_mean_growth": {
            "jul_to_aug_pct": safe_pct(m_aug["daily_open_mean"] - m_jul["daily_open_mean"], m_jul["daily_open_mean"]),
            "aug_to_sep_pct": safe_pct(m_sep["daily_open_mean"] - m_aug["daily_open_mean"], m_aug["daily_open_mean"]),
            "jul_to_sep_pct": safe_pct(m_sep["daily_open_mean"] - m_jul["daily_open_mean"], m_jul["daily_open_mean"]),
        },
        "tickets_per_active_client_growth_jul_to_sep_pct": safe_pct(
            m_sep["tickets_per_active_client"] - m_jul["tickets_per_active_client"],
            m_jul["tickets_per_active_client"],
        ),
        "duplicate_escalations_growth_jul_to_sep_pct": safe_pct(
            m_sep["duplicate_escalations"] - m_jul["duplicate_escalations"],
            m_jul["duplicate_escalations"],
        ),
    }

    # 3. Open backlog deep dive (as of 2026-09-30 23:59:59)
    open_ages = [r["open_age_hours"] for r in open_rows if r["open_age_hours"] is not None]
    open_l1_ages = [r["open_age_hours"] for r in open_l1 if r["open_age_hours"] is not None]
    open_eng_ages = [r["open_age_hours"] for r in open_eng if r["open_age_hours"] is not None]
    open_sorted_oldest = sorted(open_rows, key=lambda r: -(r["open_age_hours"] or 0.0))

    open_backlog = {
        "total_open": len(open_rows),
        "by_status": {
            "Open - with L1": len(open_l1),
            "Open - with L1 share_pct": safe_pct(len(open_l1), len(open_rows)),
            "Open - with Engineering": len(open_eng),
            "Open - with Engineering share_pct": safe_pct(len(open_eng), len(open_rows)),
        },
        "age_hours_all": {
            "median": safe_median(open_ages),
            "mean": safe_mean(open_ages),
            "min": round(min(open_ages), 2),
            "max": round(max(open_ages), 2),
            "median_days": round(statistics.median(open_ages) / 24.0, 2),
            "mean_days": round(statistics.mean(open_ages) / 24.0, 2),
            "max_days": round(max(open_ages) / 24.0, 2),
        },
        "age_hours_with_l1": {
            "median": safe_median(open_l1_ages),
            "mean": safe_mean(open_l1_ages),
            "max": round(max(open_l1_ages), 2),
        },
        "age_hours_with_engineering": {
            "median": safe_median(open_eng_ages),
            "mean": safe_mean(open_eng_ages),
            "max": round(max(open_eng_ages), 2),
        },
        "age_buckets": {
            "gt_24h": sum(1 for a in open_ages if a > 24),
            "gt_48h": sum(1 for a in open_ages if a > 48),
            "gt_72h": sum(1 for a in open_ages if a > 72),
            "gt_120h": sum(1 for a in open_ages if a > 120),
        },
        "by_priority": dict(Counter(r["priority"] for r in open_rows)),
        "by_client_tier": dict(Counter(r["client_tier"] for r in open_rows)),
        "by_eng_handoffs": {str(k): v for k, v in sorted(Counter(r["eng_handoffs"] for r in open_rows).items())},
        "by_escalated": {
            "Yes": len(open_esc),
            "No": len(open_rows) - len(open_esc),
            "escalated_share_pct": safe_pct(len(open_esc), len(open_rows)),
        },
        "by_eng_outcome": {
            (k if k else "Not escalated"): v
            for k, v in Counter(r["eng_outcome"] for r in open_rows).most_common()
        },
        "avoidable_escalated_open_count": len(open_avoid),
        "avoidable_escalated_open_share_pct": safe_pct(len(open_avoid), len(open_rows)),
        "by_category": dict(Counter(r["category"] for r in open_rows).most_common()),
        "by_agent": dict(Counter(r["assigned_agent"] for r in open_rows).most_common()),
        "oldest_10_tickets": [
            {
                "ticket_id": r["ticket_id"],
                "created_at": r["created_at"],
                "age_hours": round(r["open_age_hours"], 2),
                "age_days": round(r["open_age_hours"] / 24.0, 2),
                "priority": r["priority"],
                "status": r["status"],
                "client_name": r["client_name"],
                "client_tier": r["client_tier"],
                "category": r["category"],
                "assigned_agent": r["assigned_agent"],
                "escalated": r["escalated"],
                "eng_handoffs": r["eng_handoffs"],
                "eng_outcome": r["eng_outcome"] or None,
                "reopen_count": r["reopen_count"],
                "description": r["description"],
            }
            for r in open_sorted_oldest[:10]
        ],
    }

    # 4. Category concentration
    cat_counts = Counter(r["category"] for r in rows)
    categories_list: list[dict[str, Any]] = []
    for cat, _ in cat_counts.most_common():
        sub = [r for r in rows if r["category"] == cat]
        stats_obj = summarize_group(sub, total, len(open_rows), len(esc_rows), len(avoid_rows))
        jul_c = sum(1 for r in sub if r["created_month"] == "2026-07")
        aug_c = sum(1 for r in sub if r["created_month"] == "2026-08")
        sep_c = sum(1 for r in sub if r["created_month"] == "2026-09")
        stats_obj["category"] = cat
        stats_obj["monthly_counts"] = {"2026-07": jul_c, "2026-08": aug_c, "2026-09": sep_c}
        stats_obj["jul_to_sep_growth_pct"] = safe_pct(sep_c - jul_c, jul_c)
        stats_obj["eng_outcome_breakdown"] = {
            oc: sum(1 for r in sub if r["eng_outcome"] == oc) for oc in ALL_OUTCOME_ORDER
        }
        categories_list.append(stats_obj)

    top2_names = ["Roster / booking not syncing", "Live tracking / GPS incorrect"]
    top3_names = top2_names + ["Report export failing"]
    top2_rows = [r for r in rows if r["category"] in top2_names]
    top3_rows = [r for r in rows if r["category"] in top3_names]

    category_concentration = {
        "categories": categories_list,
        "top_2_combined": {
            "categories": top2_names,
            **summarize_group(top2_rows, total, len(open_rows), len(esc_rows), len(avoid_rows)),
            "share_of_fixed_bugs_pct": safe_pct(
                sum(1 for r in top2_rows if r["is_fixed_escalation"]), len(fixed_rows)
            ),
        },
        "top_3_combined": {
            "categories": top3_names,
            **summarize_group(top3_rows, total, len(open_rows), len(esc_rows), len(avoid_rows)),
            "share_of_fixed_bugs_pct": safe_pct(
                sum(1 for r in top3_rows if r["is_fixed_escalation"]), len(fixed_rows)
            ),
            "share_of_duplicates_pct": safe_pct(
                sum(1 for r in top3_rows if r["eng_outcome"] == "Duplicate of known issue"),
                sum(1 for r in esc_rows if r["eng_outcome"] == "Duplicate of known issue"),
            ),
        },
    }

    # 5. Escalation breakdown & eng_outcome x eng_handoffs
    outcome_rows_list: list[dict[str, Any]] = []
    for oc in ALL_OUTCOME_ORDER:
        sub_all = [r for r in esc_rows if r["eng_outcome"] == oc]
        sub_cl = [r for r in sub_all if not r["is_open"]]
        sub_op = [r for r in sub_all if r["is_open"]]
        fc_vals = [r["first_close_hours"] for r in sub_all if r["first_close_hours"] is not None]
        fin_vals = [r["final_close_hours"] for r in sub_cl if r["final_close_hours"] is not None]
        csat_vals = [float(r["csat"]) for r in sub_all if r["csat"] is not None]
        handoff_dist = {str(h): sum(1 for r in sub_all if r["eng_handoffs"] == h) for h in (1, 2, 3)}
        outcome_rows_list.append(
            {
                "eng_outcome": oc,
                "is_avoidable": oc in AVOIDABLE_OUTCOMES,
                "count_all_escalated": len(sub_all),
                "share_of_all_escalated_pct": safe_pct(len(sub_all), len(esc_rows)),
                "share_of_all_tickets_pct": safe_pct(len(sub_all), total),
                "count_closed_escalated": len(sub_cl),
                "share_of_closed_escalated_pct": safe_pct(len(sub_cl), len(closed_esc)),
                "count_open_escalated": len(sub_op),
                "first_close_hours_median": safe_median(fc_vals),
                "first_close_hours_mean": safe_mean(fc_vals),
                "final_close_hours_median": safe_median(fin_vals),
                "final_close_hours_mean": safe_mean(fin_vals),
                "total_closed_elapsed_hours": round(sum(fin_vals), 2),
                "csat_mean": safe_mean(csat_vals),
                "handoffs_distribution": handoff_dist,
            }
        )

    multi_handoff_rows = [r for r in esc_rows if r["eng_handoffs"] >= 2]
    three_handoff_rows = [r for r in esc_rows if r["eng_handoffs"] == 3]
    returned_to_l1_outcomes = {"Insufficient info - returned to L1", "Config issue - returned to L1"}

    escalation_breakdown = {
        "total_escalated": len(esc_rows),
        "closed_escalated": len(closed_esc),
        "open_escalated": len(open_esc),
        "blank_outcome_among_escalated": sum(1 for r in esc_rows if not r["eng_outcome"]),
        "fixed_all": len(fixed_rows),
        "fixed_share_of_all_escalated_pct": safe_pct(len(fixed_rows), len(esc_rows)),
        "avoidable_all": len(avoid_rows),
        "avoidable_share_of_all_escalated_pct": safe_pct(len(avoid_rows), len(esc_rows)),
        "avoidable_closed": len(closed_avoid),
        "avoidable_share_of_closed_escalated_pct": safe_pct(len(closed_avoid), len(closed_esc)),
        "avoidable_open": len(open_avoid),
        "avoidable_share_of_open_escalated_pct": safe_pct(len(open_avoid), len(open_esc)),
        "outcomes": outcome_rows_list,
        "ping_pong_root_cause": {
            "tickets_with_2plus_handoffs": len(multi_handoff_rows),
            "returned_to_l1_in_2plus_handoffs": sum(
                1 for r in multi_handoff_rows if r["eng_outcome"] in returned_to_l1_outcomes
            ),
            "returned_to_l1_share_of_2plus_handoffs_pct": safe_pct(
                sum(1 for r in multi_handoff_rows if r["eng_outcome"] in returned_to_l1_outcomes),
                len(multi_handoff_rows),
            ),
            "tickets_with_3_handoffs": len(three_handoff_rows),
            "returned_to_l1_in_3_handoffs": sum(
                1 for r in three_handoff_rows if r["eng_outcome"] in returned_to_l1_outcomes
            ),
            "returned_to_l1_share_of_3_handoffs_pct": safe_pct(
                sum(1 for r in three_handoff_rows if r["eng_outcome"] in returned_to_l1_outcomes),
                len(three_handoff_rows),
            ),
            "fixed_bugs_with_3_handoffs": sum(1 for r in three_handoff_rows if r["is_fixed_escalation"]),
        },
    }

    # 6. Resolution time impact (Escalated vs Non-escalated & by eng_handoffs & by Avoidable vs Fixed)
    def timing_block(sub: list[dict[str, Any]]) -> dict[str, Any]:
        cl = [r for r in sub if not r["is_open"]]
        fr = [r["first_response_hours"] for r in sub if r["first_response_hours"] is not None]
        fc_all = [r["first_close_hours"] for r in sub if r["first_close_hours"] is not None]
        fc_cl = [r["first_close_hours"] for r in cl if r["first_close_hours"] is not None]
        fin = [r["final_close_hours"] for r in cl if r["final_close_hours"] is not None]
        csat = [float(r["csat"]) for r in sub if r["csat"] is not None]
        return {
            "tickets": len(sub),
            "closed_tickets": len(cl),
            "open_tickets": len(sub) - len(cl),
            "first_response_hours_median": safe_median(fr),
            "first_response_hours_mean": safe_mean(fr),
            "first_close_hours_median_all_with_fc": safe_median(fc_all),
            "first_close_hours_mean_all_with_fc": safe_mean(fc_all),
            "first_close_hours_median_closed": safe_median(fc_cl),
            "first_close_hours_mean_closed": safe_mean(fc_cl),
            "final_close_hours_median": safe_median(fin),
            "final_close_hours_mean": safe_mean(fin),
            "total_closed_elapsed_hours": round(sum(fin), 2),
            "csat_mean": safe_mean(csat),
            "csat_responses": len(csat),
        }

    t_all = timing_block(rows)
    t_non_esc = timing_block(non_esc_rows)
    t_esc = timing_block(esc_rows)
    t_fixed = timing_block(fixed_rows)
    t_avoid = timing_block(avoid_rows)

    by_handoffs: list[dict[str, Any]] = []
    for h in (0, 1, 2, 3):
        sub_h = [r for r in rows if r["eng_handoffs"] == h]
        blk = timing_block(sub_h)
        blk["eng_handoffs"] = h
        blk["share_of_total_pct"] = safe_pct(len(sub_h), total)
        blk["final_close_median_multiple_vs_0"] = safe_ratio(
            blk["final_close_hours_median"], t_non_esc["final_close_hours_median"]
        )
        by_handoffs.append(blk)

    resolution_time_impact = {
        "all_tickets": t_all,
        "non_escalated": t_non_esc,
        "escalated": t_esc,
        "fixed_escalations": t_fixed,
        "avoidable_escalations": t_avoid,
        "penalties": {
            "escalated_vs_non_escalated_final_close_median_multiple": safe_ratio(
                t_esc["final_close_hours_median"], t_non_esc["final_close_hours_median"]
            ),
            "escalated_vs_non_escalated_final_close_mean_multiple": safe_ratio(
                t_esc["final_close_hours_mean"], t_non_esc["final_close_hours_mean"]
            ),
            "escalated_vs_non_escalated_first_close_median_multiple_all_with_fc": safe_ratio(
                t_esc["first_close_hours_median_all_with_fc"], t_non_esc["first_close_hours_median_all_with_fc"]
            ),
            "escalated_vs_non_escalated_first_close_median_multiple_closed": safe_ratio(
                t_esc["first_close_hours_median_closed"], t_non_esc["first_close_hours_median_closed"]
            ),
            "avoidable_vs_non_escalated_final_close_median_multiple": safe_ratio(
                t_avoid["final_close_hours_median"], t_non_esc["final_close_hours_median"]
            ),
            "avoidable_vs_fixed_final_close_median_multiple": safe_ratio(
                t_avoid["final_close_hours_median"], t_fixed["final_close_hours_median"]
            ),
            "avoidable_share_of_all_closed_elapsed_hours_pct": safe_pct(
                t_avoid["total_closed_elapsed_hours"], t_all["total_closed_elapsed_hours"]
            ),
            "escalated_csat_drop_vs_non_escalated": round(
                t_non_esc["csat_mean"] - t_esc["csat_mean"], 2
            ),
            "handoffs_3_vs_0_final_close_median_multiple": safe_ratio(
                by_handoffs[3]["final_close_hours_median"], by_handoffs[0]["final_close_hours_median"]
            ),
            "handoffs_3_vs_0_csat_drop": round(
                by_handoffs[0]["csat_mean"] - by_handoffs[3]["csat_mean"], 2
            ),
        },
        "by_eng_handoffs": by_handoffs,
    }

    # 7. Agent-level anomalies
    agents_list: list[dict[str, Any]] = []
    total_howto = sum(1 for r in esc_rows if r["eng_outcome"] == "Not a bug - how-to")
    for ag in sorted({r["assigned_agent"] for r in rows}):
        sub = [r for r in rows if r["assigned_agent"] == ag]
        sub_nonesc = [r for r in sub if not r["escalated"]]
        sub_nonesc_cl = [r for r in sub_nonesc if not r["is_open"]]
        stats_obj = summarize_group(sub, total, len(open_rows), len(esc_rows), len(avoid_rows))
        stats_obj["agent"] = ag
        stats_obj["monthly_counts"] = {
            m: sum(1 for r in sub if r["created_month"] == m) for m in ("2026-07", "2026-08", "2026-09")
        }
        stats_obj["non_escalated_first_close_hours_median"] = safe_median(
            [r["first_close_hours"] for r in sub_nonesc if r["first_close_hours"] is not None]
        )
        stats_obj["non_escalated_final_close_hours_median"] = safe_median(
            [r["final_close_hours"] for r in sub_nonesc_cl if r["final_close_hours"] is not None]
        )
        stats_obj["non_escalated_reopen_rate_all_pct"] = safe_pct(
            sum(1 for r in sub_nonesc if r["is_reopened"]), len(sub_nonesc)
        )
        stats_obj["share_of_all_reopens_pct"] = safe_pct(stats_obj["reopened_all_tickets"], len(reop_all))
        stats_obj["eng_outcome_breakdown"] = {
            oc: sum(1 for r in sub if r["eng_outcome"] == oc) for oc in ALL_OUTCOME_ORDER
        }
        stats_obj["share_of_all_howto_escalations_pct"] = safe_pct(
            stats_obj["eng_outcome_breakdown"]["Not a bug - how-to"], total_howto
        )
        agents_list.append(stats_obj)

    agents_by_name = {a["agent"]: a for a in agents_list}
    other7_excl_karan = summarize_group(
        [r for r in rows if r["assigned_agent"] != "Karan B"],
        total,
        len(open_rows),
        len(esc_rows),
        len(avoid_rows),
    )
    other7_excl_rahul = summarize_group(
        [r for r in rows if r["assigned_agent"] != "Rahul T"],
        total,
        len(open_rows),
        len(esc_rows),
        len(avoid_rows),
    )
    baseline6 = summarize_group(
        [r for r in rows if r["assigned_agent"] not in {"Karan B", "Rahul T"}],
        total,
        len(open_rows),
        len(esc_rows),
        len(avoid_rows),
    )

    agent_anomalies = {
        "agents": agents_list,
        "peer_benchmarks": {
            "other_7_excluding_karan_b": other7_excl_karan,
            "other_7_excluding_rahul_t": other7_excl_rahul,
            "baseline_6_excluding_karan_b_and_rahul_t": baseline6,
        },
        "spotlights": {
            "karan_b": {
                "tickets": agents_by_name["Karan B"]["tickets"],
                "open_tickets": agents_by_name["Karan B"]["open_tickets"],
                "first_close_hours_median_all_with_fc": agents_by_name["Karan B"]["first_close_hours_median_all_with_fc"],
                "other_7_first_close_hours_median": other7_excl_karan["first_close_hours_median_all_with_fc"],
                "non_escalated_first_close_hours_median": agents_by_name["Karan B"]["non_escalated_first_close_hours_median"],
                "final_close_hours_median": agents_by_name["Karan B"]["final_close_hours_median"],
                "reopened_all_tickets": agents_by_name["Karan B"]["reopened_all_tickets"],
                "reopen_rate_all_pct": agents_by_name["Karan B"]["reopen_rate_all_pct"],
                "reopen_rate_closed_pct": agents_by_name["Karan B"]["reopen_rate_closed_pct"],
                "other_7_reopen_rate_all_pct": other7_excl_karan["reopen_rate_all_pct"],
                "reopen_rate_multiple_vs_other_7": safe_ratio(
                    agents_by_name["Karan B"]["reopen_rate_all_pct"], other7_excl_karan["reopen_rate_all_pct"]
                ),
                "share_of_company_reopens_pct": agents_by_name["Karan B"]["share_of_all_reopens_pct"],
                "csat_mean": agents_by_name["Karan B"]["csat_mean"],
                "other_7_csat_mean": other7_excl_karan["csat_mean"],
                "escalation_rate_pct": agents_by_name["Karan B"]["escalation_rate_pct"],
            },
            "rahul_t": {
                "tickets": agents_by_name["Rahul T"]["tickets"],
                "share_of_total_tickets_pct": agents_by_name["Rahul T"]["share_of_total_pct"],
                "escalated_tickets": agents_by_name["Rahul T"]["escalated_tickets"],
                "escalation_rate_pct": agents_by_name["Rahul T"]["escalation_rate_pct"],
                "other_7_escalation_rate_pct": other7_excl_rahul["escalation_rate_pct"],
                "escalation_rate_multiple_vs_other_7": safe_ratio(
                    agents_by_name["Rahul T"]["escalation_rate_pct"], other7_excl_rahul["escalation_rate_pct"]
                ),
                "share_of_all_escalations_pct": agents_by_name["Rahul T"]["share_of_all_escalations_pct"],
                "avoidable_escalations": agents_by_name["Rahul T"]["avoidable_escalations"],
                "avoidable_share_of_his_escalations_pct": agents_by_name["Rahul T"]["avoidable_share_of_group_escalations_pct"],
                "other_7_avoidable_share_pct": other7_excl_rahul["avoidable_share_of_group_escalations_pct"],
                "share_of_all_avoidable_escalations_pct": agents_by_name["Rahul T"]["share_of_all_avoidable_escalations_pct"],
                "howto_escalations": agents_by_name["Rahul T"]["eng_outcome_breakdown"]["Not a bug - how-to"],
                "company_total_howto_escalations": total_howto,
                "share_of_company_howto_escalations_pct": agents_by_name["Rahul T"]["share_of_all_howto_escalations_pct"],
                "config_issue_escalations": agents_by_name["Rahul T"]["eng_outcome_breakdown"]["Config issue - returned to L1"],
                "insufficient_info_escalations": agents_by_name["Rahul T"]["eng_outcome_breakdown"]["Insufficient info - returned to L1"],
                "final_close_hours_median": agents_by_name["Rahul T"]["final_close_hours_median"],
                "true_fcr_rate_closed_pct": agents_by_name["Rahul T"]["true_fcr_rate_closed_pct"],
                "csat_mean": agents_by_name["Rahul T"]["csat_mean"],
            },
        },
    }

    # 8. Top affected clients
    by_client: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_client[(r["client_id"], r["client_name"], r["client_tier"])].append(r)

    client_records: list[dict[str, Any]] = []
    for (cid, cname, tier), sub in by_client.items():
        grp = summarize_group(sub, total, len(open_rows), len(esc_rows), len(avoid_rows))
        client_records.append(
            {
                "client_id": cid,
                "client_name": cname,
                "client_tier": tier,
                "tickets": grp["tickets"],
                "open_tickets": grp["open_tickets"],
                "escalated_tickets": grp["escalated_tickets"],
                "escalation_rate_pct": grp["escalation_rate_pct"],
                "avoidable_escalations": grp["avoidable_escalations"],
                "avoidable_share_of_client_escalations_pct": grp["avoidable_share_of_group_escalations_pct"],
                "reopened_tickets": grp["reopened_all_tickets"],
                "reopen_rate_all_pct": grp["reopen_rate_all_pct"],
                "final_close_hours_median": grp["final_close_hours_median"],
                "csat_mean": grp["csat_mean"],
                "csat_responses": grp["csat_responses"],
            }
        )

    top_clients = {
        "unique_clients_total": len(client_records),
        "clients_with_open_tickets": sum(1 for c in client_records if c["open_tickets"] > 0),
        "top_15_by_volume": sorted(client_records, key=lambda c: (-c["tickets"], -c["open_tickets"], c["client_id"]))[:15],
        "top_10_by_open_backlog": sorted(client_records, key=lambda c: (-c["open_tickets"], -c["tickets"], c["client_id"]))[:10],
        "top_10_by_avoidable_escalations": sorted(
            client_records, key=lambda c: (-c["avoidable_escalations"], -c["escalated_tickets"], c["client_id"])
        )[:10],
        "lowest_10_csat_min_5_responses": sorted(
            [c for c in client_records if c["csat_responses"] >= 5 and c["csat_mean"] is not None],
            key=lambda c: (c["csat_mean"], -c["tickets"], c["client_id"]),
        )[:10],
    }

    # 9. Recurring eng_ticket_id & description patterns (duplicate detection)
    dup_rows = [r for r in esc_rows if r["eng_outcome"] == "Duplicate of known issue"]
    nd_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        nd_groups[(r["category"], r["normalized_description"])].append(r)

    top_norm_clusters: list[dict[str, Any]] = []
    for (cat, nd), sub in sorted(nd_groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        esc_c = sum(1 for r in sub if r["escalated"])
        dup_c = sum(1 for r in sub if r["eng_outcome"] == "Duplicate of known issue")
        avoid_c = sum(1 for r in sub if r["is_avoidable_escalation"])
        fixed_c = sum(1 for r in sub if r["is_fixed_escalation"])
        op_c = sum(1 for r in sub if r["is_open"])
        sample_desc = Counter(r["description"] for r in sub).most_common(1)[0][0]
        top_norm_clusters.append(
            {
                "category": cat,
                "normalized_description": nd,
                "sample_description": sample_desc,
                "tickets": len(sub),
                "open_tickets": op_c,
                "escalated_tickets": esc_c,
                "escalation_rate_pct": safe_pct(esc_c, len(sub)),
                "fixed_escalations": fixed_c,
                "avoidable_escalations": avoid_c,
                "duplicate_escalations": dup_c,
            }
        )

    dup_by_cluster: list[dict[str, Any]] = []
    dup_nd_map: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in dup_rows:
        dup_nd_map[(r["category"], r["normalized_description"])].append(r)
    for (cat, nd), sub in sorted(dup_nd_map.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        dup_by_cluster.append(
            {
                "category": cat,
                "normalized_description": nd,
                "duplicate_count": len(sub),
                "open_duplicates": sum(1 for r in sub if r["is_open"]),
                "sample_eng_ticket_ids": [r["eng_ticket_id"] for r in sub[:5]],
                "sample_description": sub[0]["description"],
            }
        )

    recurring_patterns = {
        "eng_ticket_id_analysis": {
            "total_escalated_tickets": len(esc_rows),
            "unique_eng_ticket_ids": len(set(eng_ticket_ids)),
            "shared_or_reused_eng_ticket_ids": sum(1 for _, c in Counter(eng_ticket_ids).items() if c > 1),
            "finding": (
                "100% of escalated tickets (486/486) receive a brand-new unique eng_ticket_id (0 shared IDs), "
                "even for the 56 'Duplicate of known issue' escalations — proving L1 has no known-issue linking."
            ),
        },
        "unique_raw_descriptions": len({r["description"] for r in rows}),
        "unique_normalized_description_templates": len(nd_groups),
        "duplicate_of_known_issue_summary": {
            "total_duplicates": len(dup_rows),
            "share_of_escalated_pct": safe_pct(len(dup_rows), len(esc_rows)),
            "by_month": {m: sum(1 for r in dup_rows if r["created_month"] == m) for m in ("2026-07", "2026-08", "2026-09")},
            "by_category": dict(Counter(r["category"] for r in dup_rows).most_common()),
            "top_duplicate_clusters": dup_by_cluster[:15],
        },
        "top_20_normalized_description_clusters": top_norm_clusters[:20],
    }

    # 10. Additional breakdowns: Channel, Priority, Client Tier, Reopen Impact
    def dimension_breakdown(field: str) -> list[dict[str, Any]]:
        out = []
        for val, _ in Counter(r[field] for r in rows).most_common():
            sub = [r for r in rows if r[field] == val]
            grp = summarize_group(sub, total, len(open_rows), len(esc_rows), len(avoid_rows))
            grp[field] = val
            out.append(grp)
        return out

    reop_closed_extra = [r["reopen_extra_hours"] for r in reop_closed if r["reopen_extra_hours"] is not None]
    karan_reop_closed_extra = [
        r["reopen_extra_hours"]
        for r in reop_closed
        if r["assigned_agent"] == "Karan B" and r["reopen_extra_hours"] is not None
    ]
    reop_timing = timing_block(reop_all)
    non_reop_timing = timing_block([r for r in rows if not r["is_reopened"]])

    reopen_impact = {
        "reopened_tickets": reop_timing,
        "never_reopened_tickets": non_reop_timing,
        "extra_hours_after_first_close_closed_reopened": {
            "count": len(reop_closed_extra),
            "median_hours": safe_median(reop_closed_extra),
            "mean_hours": safe_mean(reop_closed_extra),
            "total_hours": round(sum(reop_closed_extra), 2),
        },
        "karan_b_extra_hours_closed_reopened": {
            "count": len(karan_reop_closed_extra),
            "median_hours": safe_median(karan_reop_closed_extra),
            "mean_hours": safe_mean(karan_reop_closed_extra),
            "total_hours": round(sum(karan_reop_closed_extra), 2),
        },
        "csat_drop_when_reopened": round(non_reop_timing["csat_mean"] - reop_timing["csat_mean"], 2),
    }

    # 11. What-If Impact Simulator baseline parameters & transparent example scenarios
    # Compute all intermediate quantities from unrounded floats to avoid rounding drift.
    raw_non_esc_fin = [r["final_close_hours"] for r in non_esc_rows if r["final_close_hours"] is not None]
    raw_avoid_fin = [r["final_close_hours"] for r in closed_avoid if r["final_close_hours"] is not None]
    raw_mean_non_esc_h = statistics.mean(raw_non_esc_fin)
    raw_med_non_esc_h = statistics.median(raw_non_esc_fin)
    raw_mean_avoid_h = statistics.mean(raw_avoid_fin)
    raw_med_avoid_h = statistics.median(raw_avoid_fin)
    raw_avoid_closed_total_h = sum(raw_avoid_fin)
    raw_excess_per_avoid_mean_h = raw_mean_avoid_h - raw_mean_non_esc_h
    raw_excess_per_avoid_med_h = raw_med_avoid_h - raw_med_non_esc_h
    raw_excess_closed_vs_mean_h = raw_avoid_closed_total_h - (len(closed_avoid) * raw_mean_non_esc_h)
    raw_excess_all_extrap_vs_mean_h = len(avoid_rows) * raw_excess_per_avoid_mean_h
    raw_mean_reop_extra = statistics.mean(reop_closed_extra) if reop_closed_extra else 0.0

    mean_non_esc_h = round(raw_mean_non_esc_h, 2)
    med_non_esc_h = round(raw_med_non_esc_h, 2)
    mean_avoid_h = round(raw_mean_avoid_h, 2)
    med_avoid_h = round(raw_med_avoid_h, 2)
    avoid_closed_total_h = round(raw_avoid_closed_total_h, 2)
    excess_per_avoid_mean_h = round(raw_excess_per_avoid_mean_h, 2)
    excess_per_avoid_med_h = round(raw_excess_per_avoid_med_h, 2)
    excess_closed_vs_mean_h = round(raw_excess_closed_vs_mean_h, 2)
    excess_all_extrap_vs_mean_h = round(raw_excess_all_extrap_vs_mean_h, 2)

    # September steady-state Little's Law baseline
    sep_arrival_per_hr = m_sep["tickets_created"] / (m_sep["observed_days"] * 24.0)
    sep_avoid_count = m_sep["avoidable_escalations"]
    sep_avoid_share_of_sep_tickets = sep_avoid_count / m_sep["tickets_created"]
    sep_mean_w = m_sep["final_close_hours_mean"]
    overall_mean_w = t_all["final_close_hours_mean"]

    def build_whatif_scenario(avoidable_deflection_pct: float, reopen_reduction_pct: float = 0.0) -> dict[str, Any]:
        """Transparent formula matching the app What-If Simulator (full-precision intermediates)."""
        frac_deflect = avoidable_deflection_pct / 100.0
        frac_reop = reopen_reduction_pct / 100.0

        # 1. Quarterly (3-month) & Sep monthly tickets deflected from Engineering
        q_avoid_deflected = len(avoid_rows) * frac_deflect
        m_sep_avoid_deflected = sep_avoid_count * frac_deflect

        # 2. Elapsed ticket-hours saved (quarterly & monthly Sep run-rate)
        q_hours_saved_avoid = len(avoid_rows) * frac_deflect * raw_excess_per_avoid_mean_h
        m_sep_hours_saved_avoid = sep_avoid_count * frac_deflect * raw_excess_per_avoid_mean_h

        # 3. Reopen hours saved (using unrounded closed reopened mean extra hours)
        q_hours_saved_reopen = len(reop_all) * frac_reop * raw_mean_reop_extra
        m_sep_hours_saved_reopen = m_sep["reopened_tickets"] * frac_reop * raw_mean_reop_extra

        # 4. Open backlog reduction (two transparent methods):
        # Method A (Direct snapshot): avoidable escalated open tickets (22) * deflection%
        direct_open_saved = len(open_avoid) * frac_deflect
        direct_open_after = len(open_rows) - direct_open_saved

        # Method B (Little's Law steady-state at Sep arrival rate):
        sep_reop_share = m_sep["reopened_tickets"] / m_sep["tickets_created"]
        delta_w_hours = (sep_avoid_share_of_sep_tickets * frac_deflect * raw_excess_per_avoid_mean_h) + (
            sep_reop_share * frac_reop * raw_mean_reop_extra
        )
        littles_open_saved = sep_arrival_per_hr * delta_w_hours
        littles_open_after_from_sep48 = max(0.0, len(open_rows) - littles_open_saved)
        littles_open_reduction_pct = safe_pct(littles_open_saved, len(open_rows))

        # 5. New Avoidable Escalation Rate (of total escalated tickets)
        new_avoid_count = len(avoid_rows) * (1.0 - frac_deflect)
        new_esc_total = len(fixed_rows) + new_avoid_count
        new_avoid_share_of_esc = safe_pct(new_avoid_count, new_esc_total)
        new_overall_esc_rate = safe_pct(new_esc_total, total)

        return {
            "avoidable_deflection_pct": avoidable_deflection_pct,
            "reopen_reduction_pct": reopen_reduction_pct,
            "quarterly_eng_tickets_deflected": round(q_avoid_deflected, 1),
            "monthly_sep_eng_tickets_deflected": round(m_sep_avoid_deflected, 1),
            "quarterly_elapsed_hours_saved_avoidable": round(q_hours_saved_avoid, 1),
            "monthly_sep_elapsed_hours_saved_avoidable": round(m_sep_hours_saved_avoid, 1),
            "quarterly_elapsed_hours_saved_reopens": round(q_hours_saved_reopen, 1),
            "monthly_sep_elapsed_hours_saved_reopens": round(m_sep_hours_saved_reopen, 1),
            "monthly_sep_total_elapsed_hours_saved": round(m_sep_hours_saved_avoid + m_sep_hours_saved_reopen, 1),
            "avg_resolution_hours_reduction_delta_w": round(delta_w_hours, 2),
            "direct_snapshot_open_backlog_saved": round(direct_open_saved, 1),
            "direct_snapshot_open_backlog_after": round(direct_open_after, 1),
            "littles_law_steady_state_open_saved": round(littles_open_saved, 1),
            "littles_law_open_after_from_48": round(littles_open_after_from_sep48, 1),
            "littles_law_open_reduction_pct_from_48": littles_open_reduction_pct,
            "new_escalation_rate_pct": new_overall_esc_rate,
            "new_avoidable_share_of_escalated_pct": new_avoid_share_of_esc,
        }

    what_if_baseline = {
        "parameters": {
            "total_tickets_3mo": total,
            "sep_tickets": m_sep["tickets_created"],
            "sep_observed_days": m_sep["observed_days"],
            "sep_arrival_rate_per_hour": round(sep_arrival_per_hr, 4),
            "sep_eom_open_backlog": len(open_rows),
            "sep_open_avoidable_escalated": len(open_avoid),
            "avoidable_escalations_3mo_all": len(avoid_rows),
            "avoidable_escalations_3mo_closed": len(closed_avoid),
            "avoidable_escalations_sep": sep_avoid_count,
            "non_escalated_final_close_mean_hours": mean_non_esc_h,
            "non_escalated_final_close_median_hours": med_non_esc_h,
            "avoidable_escalated_final_close_mean_hours": mean_avoid_h,
            "avoidable_escalated_final_close_median_hours": med_avoid_h,
            "excess_hours_per_avoidable_escalation_mean": excess_per_avoid_mean_h,
            "excess_hours_per_avoidable_escalation_median": excess_per_avoid_med_h,
            "total_closed_avoidable_elapsed_hours": avoid_closed_total_h,
            "total_closed_excess_hours_vs_non_esc_mean": excess_closed_vs_mean_h,
            "extrapolated_all_275_excess_hours_vs_non_esc_mean": excess_all_extrap_vs_mean_h,
            "all_closed_mean_resolution_hours": overall_mean_w,
            "sep_closed_mean_resolution_hours": sep_mean_w,
            "reopened_mean_extra_hours": safe_mean(reop_closed_extra),
            "reopened_total_extra_hours_closed": round(sum(reop_closed_extra), 2),
        },
        "formulas": {
            "excess_hours_per_avoidable_ticket": "mean_final_close(avoidable_escalated_closed) - mean_final_close(non_escalated_closed)",
            "littles_law_backlog_reduction": "sep_arrival_rate_per_hour * ((sep_avoidable / sep_tickets) * deflection_frac * excess_hours_per_avoidable + (sep_reopened / sep_tickets) * reopen_red_frac * mean_reopen_extra_hours)",
            "direct_snapshot_backlog_reduction": "sep_open_avoidable_escalated (22) * deflection_frac",
        },
        "example_scenarios": {
            "conservative_40pct_avoidable_deflection": build_whatif_scenario(40.0, 0.0),
            "target_50pct_avoidable_deflection_30pct_reopen_reduction": build_whatif_scenario(50.0, 30.0),
            "stretch_65pct_avoidable_deflection_40pct_reopen_reduction": build_whatif_scenario(65.0, 40.0),
        },
    }

    methodology = {
        "source_csv": str(CSV_PATH.name),
        "data_pull_reference_ist": DATA_PULL_ISO,
        "avoidable_escalation_outcomes": sorted(AVOIDABLE_OUTCOMES),
        "avoidable_escalation_primary_denominator": "all_escalated_tickets (n=486, since 0 escalated tickets have blank eng_outcome); closed_escalated (n=452) also reported",
        "reopen_rate_denominators": "reopen_rate_all_pct uses all tickets (n=1444); reopen_rate_closed_pct uses closed tickets (n=1396); both reported",
        "true_fcr_definition": "status == 'Closed' AND escalated_to_eng == 'No' AND reopen_count == 0; primary denominator = closed tickets (n=1396), secondary = all tickets (n=1444)",
        "resolution_hours_definition": {
            "first_response_hours": "(first_response_at - created_at) in hours on non-blank first_response_at (n=1439)",
            "first_close_hours": "(first_closed_at - created_at) in hours on non-blank first_closed_at (n=1402) and closed-only (n=1396)",
            "final_close_hours": "(final_closed_at - created_at) in hours on closed tickets (n=1396)",
            "open_age_hours": "(2026-09-30 23:59:59 - created_at) in hours on open tickets (n=48)",
        },
        "eom_open_backlog_definition": "tickets with created_at <= month_end 23:59:59 AND (final_closed_at is blank OR final_closed_at > month_end 23:59:59)",
    }

    return {
        "methodology": methodology,
        "overview": overview,
        "monthly_trends": monthly_trends,
        "open_backlog": open_backlog,
        "category_concentration": category_concentration,
        "escalation_breakdown": escalation_breakdown,
        "resolution_time_impact": resolution_time_impact,
        "agent_anomalies": agent_anomalies,
        "top_clients": top_clients,
        "recurring_patterns": recurring_patterns,
        "by_channel": dimension_breakdown("channel"),
        "by_priority": dimension_breakdown("priority"),
        "by_client_tier": dimension_breakdown("client_tier"),
        "reopen_impact": reopen_impact,
        "what_if_baseline": what_if_baseline,
    }


def print_markdown_summary(m: dict[str, Any]) -> None:
    ov = m["overview"]
    mt = m["monthly_trends"]
    ob = m["open_backlog"]
    eb = m["escalation_breakdown"]
    rt = m["resolution_time_impact"]
    sp = m["agent_anomalies"]["spotlights"]
    top2 = m["category_concentration"]["top_2_combined"]
    wf = m["what_if_baseline"]["parameters"]

    print("# RideOps Support — Programmatic Diagnostic Summary\n")
    print(f"- **Dataset**: {ov['total_tickets']:,} tickets ({ov['date_range']['created_at_min']} to {ov['date_range']['created_at_max']} IST; pull ref `{ov['date_range']['data_pull_reference_ist']}`)")
    print(f"- **Open Backlog (Sep 30)**: **{ov['open_tickets']}** ({ov['open_with_l1']} Open - with L1, {ov['open_with_engineering']} Open - with Engineering; **{ov['open_escalated_share_pct']}%** escalated; **{ov['open_avoidable_share_of_open_pct']}%** avoidable escalated)")
    print(
        f"- **Monthly Volume**: Jul `{mt['months'][0]['tickets_created']}` -> Aug `{mt['months'][1]['tickets_created']}` ({mt['volume_growth']['jul_to_aug_pct']:+.2f}%) -> Sep `{mt['months'][2]['tickets_created']}` ({mt['volume_growth']['aug_to_sep_pct']:+.2f}%) | **Jul->Sep: {mt['volume_growth']['jul_to_sep_pct']:+.2f}%**"
    )
    print(
        f"- **End-of-Month Open Backlog**: Jul 31 `{mt['months'][0]['eom_open_backlog']}` -> Aug 31 `{mt['months'][1]['eom_open_backlog']}` ({mt['eom_open_backlog_growth']['jul_to_aug_pct']:+.2f}%) -> Sep 30 `{mt['months'][2]['eom_open_backlog']}` ({mt['eom_open_backlog_growth']['aug_to_sep_pct']:+.2f}%) | **Jul->Sep: {mt['eom_open_backlog_growth']['jul_to_sep_pct']:+.2f}%**"
    )
    print(
        f"- **Escalations**: `{eb['total_escalated']}/{ov['total_tickets']}` ({ov['escalation_rate_pct']}%) | `Fixed`: `{eb['fixed_all']}` ({eb['fixed_share_of_all_escalated_pct']}%) | **Avoidable**: `{eb['avoidable_all']}/{eb['total_escalated']}` (**{eb['avoidable_share_of_all_escalated_pct']}%** all; `{eb['avoidable_closed']}/{eb['closed_escalated']}` = {eb['avoidable_share_of_closed_escalated_pct']}% closed)"
    )
    print(
        f"- **Resolution Penalty**: Non-escalated median `{rt['non_escalated']['final_close_hours_median']}h` vs Escalated median `{rt['escalated']['final_close_hours_median']}h` (**{rt['penalties']['escalated_vs_non_escalated_final_close_median_multiple']}x**) | Avoidable median `{rt['avoidable_escalations']['final_close_hours_median']}h` vs Fixed median `{rt['fixed_escalations']['final_close_hours_median']}h`"
    )
    print(
        f"- **Handoff Ping-Pong**: 0h=`{rt['by_eng_handoffs'][0]['final_close_hours_median']}h` (CSAT {rt['by_eng_handoffs'][0]['csat_mean']}) -> 1h=`{rt['by_eng_handoffs'][1]['final_close_hours_median']}h` -> 2h=`{rt['by_eng_handoffs'][2]['final_close_hours_median']}h` -> 3h=`{rt['by_eng_handoffs'][3]['final_close_hours_median']}h` (CSAT {rt['by_eng_handoffs'][3]['csat_mean']}; **{rt['penalties']['handoffs_3_vs_0_final_close_median_multiple']}x**)"
    )
    print(
        f"- **Top 2 Categories** ({' + '.join(top2['categories'])}): `{top2['tickets']}/{ov['total_tickets']}` ({top2['share_of_total_pct']}%) volume, `{top2['open_tickets']}/{ob['total_open']}` ({top2['share_of_open_pct']}%) open backlog, `{top2['escalated_tickets']}/{eb['total_escalated']}` ({top2['share_of_all_escalations_pct']}%) escalations, `{top2['avoidable_escalations']}/{eb['avoidable_all']}` ({top2['share_of_all_avoidable_escalations_pct']}%) avoidable"
    )
    print(
        f"- **Karan B Anomaly**: Median first-close `{sp['karan_b']['first_close_hours_median_all_with_fc']}h` (vs `{sp['karan_b']['other_7_first_close_hours_median']}h` peers), Reopen rate `{sp['karan_b']['reopen_rate_all_pct']}%` all / `{sp['karan_b']['reopen_rate_closed_pct']}%` closed (vs `{sp['karan_b']['other_7_reopen_rate_all_pct']}%` peers; **{sp['karan_b']['reopen_rate_multiple_vs_other_7']}x**; `{sp['karan_b']['share_of_company_reopens_pct']}%` of all company reopens), CSAT `{sp['karan_b']['csat_mean']}` (vs `{sp['karan_b']['other_7_csat_mean']}`)"
    )
    print(
        f"- **Rahul T Anomaly**: Escalation rate `{sp['rahul_t']['escalation_rate_pct']}%` (`{sp['rahul_t']['escalated_tickets']}/{sp['rahul_t']['tickets']}` vs `{sp['rahul_t']['other_7_escalation_rate_pct']}%` peers; **{sp['rahul_t']['escalation_rate_multiple_vs_other_7']}x**), Avoidable share `{sp['rahul_t']['avoidable_share_of_his_escalations_pct']}%` (`{sp['rahul_t']['avoidable_escalations']}/{sp['rahul_t']['escalated_tickets']}`), `Not a bug - how-to`: `{sp['rahul_t']['howto_escalations']}/{sp['rahul_t']['company_total_howto_escalations']}` (**{sp['rahul_t']['share_of_company_howto_escalations_pct']}%** of entire company!)"
    )
    print(
        f"- **True FCR**: `{ov['true_fcr_tickets']}/{ov['closed_tickets']}` closed (**{ov['true_fcr_rate_closed_pct']}%**) | Overall Reopen Rate: `{ov['reopened_tickets_all']}/{ov['total_tickets']}` (**{ov['reopen_rate_all_pct']}%** all, **{ov['reopen_rate_closed_pct']}%** closed)"
    )
    print(
        f"- **What-If Baseline**: `{wf['excess_hours_per_avoidable_escalation_mean']}h` mean excess elapsed time per avoidable escalation -> `{wf['total_closed_excess_hours_vs_non_esc_mean']:,.1f}h` wasted on closed avoidable escalations (`{wf['extrapolated_all_275_excess_hours_vs_non_esc_mean']:,.1f}h` across all 275)."
    )
    print(f"\nSaved full structured metrics to `{OUTPUT_JSON}`")


def main() -> None:
    rows = load_tickets(CSV_PATH)
    metrics = compute_metrics(rows)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print_markdown_summary(metrics)


if __name__ == "__main__":
    main()
