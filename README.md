# RideOps Support — Triage & Escalation Gatekeeper (v0)

MoveInSync Forward-Deployed Engineer (FDE) Case Study submission for **RideOps Support**.

This repository contains:
1. **Programmatic Data Diagnosis** (`analysis/diagnose.py` + `analysis/metrics_summary.json`) — reproducible, zero-hardcoded analysis of all `1,444` support tickets (`rideops_support_tickets.csv`).
2. **Working v0 Internal Tool** (`app.py` + `src/`) — **RideOps Triage & Escalation Gatekeeper (v0)**, a Streamlit application built for L1 Support Agents (with a weekly Ops Pulse & Coaching view for Support & Operations leadership) designed to cut avoidable escalations (`56.58%` baseline) and open backlog (`48` open, `+60.00%` Jul→Sep) at `$0` new hiring cost.
3. **Executive Write-Up** ([SUBMISSION_WRITEUP.md](SUBMISSION_WRITEUP.md)) — concise 8-slide / <4-page memo covering diagnosis, North Star & Guardrail metrics, v0 architecture, projected impact, 4-week roadmap, and explicit trade-offs.

---

## Live Demo

- **Streamlit Community Cloud URL:** `[ADD LIVE STREAMLIT COMMUNITY CLOUD URL HERE]`
- **2-Minute Cloud Deploy:** Push this repository to GitHub → visit [share.streamlit.io](https://share.streamlit.io) → click **New app** → select repo & branch, set Main file path to `app.py` → click **Deploy** (`requirements.txt` and `.streamlit/config.toml` are preconfigured with lightweight packages only: `streamlit`, `pandas`, `numpy`, `plotly`).

---

## Quickstart (Local)

> Recommended: run inside a fresh Python virtual environment (`python3 -m venv .venv && source .venv/bin/activate`).

### 1. Run the Working v0 App
```bash
pip install -r requirements.txt && streamlit run app.py
```
Opens **RideOps Triage & Escalation Gatekeeper (v0)** in your browser with three interactive tabs:
- **1. Live Open Queue:** All `48` open tickets ranked by Urgency Score (`0–100`), with **Ping-Pong Risk (`>=2` handoffs)** & **Stale (`>48h`)** badges, inline Duplicate Radar preview, and 1-click triage handoff.
- **2. Escalation Gatekeeper & Duplicate Radar:** Live TF-IDF cosine similarity search over all `486` historical `ENG-xxxx` escalations, tailored L1 runbooks & mandatory preflight checks for all `10` ticket categories, a **Hard Escalation Gate** (disabled until all checks & diagnostic fields pass), an **L1 Closure Quality Guardrail** (blocking premature closures), and copy-ready Engineering Handoff Briefs with live session KPI updates.
- **3. Ops Pulse & Coaching View:** Four dynamic Plotly charts (Monthly Volume vs EOM Open Backlog, Escalation Waste Breakdown, Handoff Ping-Pong Penalty, Agent Quality vs Speed Quadrant with `<8%` Reopen Guardrail), dynamic coaching callouts, and an interactive **What-If Impact Simulator**.

### 2. Re-Run the Programmatic Diagnosis Script (Zero External Dependencies)
```bash
python3 analysis/diagnose.py
```
Recomputes every statistic directly from `rideops_support_tickets.csv` using Python stdlib only, writes `analysis/metrics_summary.json`, and prints a clean summary to stdout.

---

## Repository Structure

```text
rideops-case-study/
├── .gitignore                      # Excludes local venv, caches, and original brief PDF
├── rideops_support_tickets.csv     # Raw dataset (1,444 tickets, 2 Jul – 30 Sep 2026)
├── rideops_data_dictionary.csv     # Column definitions
├── README.md                       # Repository overview & quickstart guide
├── SUBMISSION_WRITEUP.md           # 8-slide / <4-page executive write-up
├── app.py                          # Streamlit v0 app (RideOps Triage & Escalation Gatekeeper)
├── requirements.txt                # Lightweight Python dependencies for local & Cloud deploy
├── .streamlit/
│   └── config.toml                 # Light/slate executive theme & headless defaults
├── analysis/
│   ├── diagnose.py                 # Zero-dependency stdlib diagnosis script
│   └── metrics_summary.json        # Programmatically generated single source of truth
└── src/
    ├── __init__.py                 # Package marker
    ├── metrics.py                  # Dynamic CSV metrics, Urgency Queue & What-If Simulator
    ├── duplicate_radar.py          # Pure-NumPy TF-IDF cosine similarity Duplicate Radar
    ├── runbooks.py                 # All 10 category L1 runbooks, closure guardrail & brief builders
    └── charts.py                   # 4 executive Plotly charts for Tab 3 (Ops Pulse)
```
