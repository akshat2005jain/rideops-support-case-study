# RideOps Support — Backlog Diagnosis, v0 Gatekeeper & 4-Week Plan

**MoveInSync FDE Case Study** | **Data:** `1,444` tickets (`2 Jul–30 Sep 2026`, pull `2026-09-30 23:59:59` IST) | **Budget:** `$0` new hires

---

## Slide 1: Executive Summary

**The Ask:** Open tickets are *"up about 60% since July"* and clients are noticing. Bring backlog down this quarter with **no budget for new hires** (Ritika, Head of Ops).

**The Real Problem:**
1. **Backlog explosion is driven by escalation leakage, not headcount:** Monthly volume rose **+51.79%** Jul→Sep (`390 → 592`) and end-of-month open backlog jumped **+60.00%** (`30 → 48`). Yet **60.42%** (`29/48`) of open tickets sit with L1, and **70.83%** (`34/48`) are escalated.
2. **56.58% of escalations are avoidable waste:** Of **486** escalations (`33.66%` of volume), **275 (56.58%)** are non-bugs. Worse, avoidable escalations close **1.59x slower** than real `Fixed` bugs (**103.13h** vs **64.83h** median) and consume **46.06%** (`29,453.63h` of `63,943.47h`) of all closed ticket-hours.
3. **Two coachable agent outliers distort both leadership narratives:** **Karan B** drives **42.38%** of all company reopens (`64/151`) via premature closures; **Rahul T** drives **25.45%** of all avoidable escalations (`70/275`) and **75.00%** (`18/24`) of all `Not a bug - how-to` escalations.

**The `$0` Fix:** Launch **RideOps Triage & Escalation Gatekeeper (v0)** for L1 agents (Duplicate Radar + category runbooks + Hard Escalation Gate + L1 Closure Quality Guardrail) paired with targeted Karan B / Rahul T coaching. At target (**50%** avoidable deflection, **30%** reopen cut): **55.5** fewer escalations/mo (Sep rate), **6,277.2** elapsed queue hours reclaimed/mo (**132.0** active Eng+L1 hrs/mo), and **-18.16%** steady-state open backlog (`48 → 39.3`; direct `-22.92%`, `48 → 37.0`) at **`$0` hiring cost**.

---

## Slide 2: Data Diagnosis — Why Backlog Exploded

- **Volume & Backlog (`1,444` total = `1,396` Closed, `48` Open: `29` L1 / `19` Eng):** Monthly created tickets climbed Jul **390** → Aug **462** (`+18.46%`) → Sep **592** (`+28.14%`; **+51.79%** Jul→Sep, `+202`) as tickets/active client rose `2.57 → 3.10 → 3.54` (`+37.74%`, `191` clients). EOM open backlog grew Jul 31 **30** → Aug 31 **23** → Sep 30 **48** (**+60.00%**); mean daily open doubled (`20.83 → 42.90`, **+105.95%**). Open median age is **51.66h** (`25/48` stale `>48h`; `22/48` ping-pong `>=2` handoffs; oldest `SUP-11258` at **222.65h / 9.28d**, P1 GPS on Rahul T, `3` handoffs).
- **Escalation Penalty (`6.90x` Median Slowdown) & Avoidable Split (`n=486`, `0` blank):** Escalated tickets take **86.78h** median (`99.79h` mean, CSAT **3.11**) vs **12.57h** (`19.96h` mean, CSAT **4.01**) for L1-resolved (**6.90x** median / **5.00x** mean; **-0.90** CSAT). Avoidable share = **56.58%** all (`275/486`), **55.97%** closed (`253/452`), **64.71%** open (`22/34`):

| `eng_outcome` | Bucket | Count | % of 486 | Open | Med Final Close | Avg CSAT |
|---|---|---:|---:|---:|---:|---:|
| `Fixed` | Valid Bug | 211 | 43.42% | 12 | 64.83h | 3.41 |
| `Insufficient info - returned to L1` | Avoidable | 89 | 18.31% | 10 | **121.12h** | **2.66** |
| `Config issue - returned to L1` | Avoidable | 84 | 17.28% | 8 | **128.57h** | **2.43** |
| `Duplicate of known issue` | Avoidable | 56 | 11.52% | 2 | 67.49h | 3.47 |
| `Not a bug - how-to` | Avoidable | 24 | 4.94% | 1 | 68.67h | 3.20 |
| `Not reproducible` | Avoidable | 22 | 4.53% | 1 | 62.30h | 3.40 |
| **Total Avoidable (5 Non-Fixed)** | **Waste** | **275** | **56.58%** | **22** | **103.13h** | **2.89** |

- **Handoff Ping-Pong Tax:** Median close by `eng_handoffs`: `0` (`n=958`): **12.57h** (`1.00x`, CSAT `4.01`) → `1` (`n=257`): **58.65h** (**4.67x**, `3.56`) → `2` (`n=167`): **110.37h** (**8.78x**, `2.80`) → `3` (`n=62`): **169.91h** (**13.52x**, `2.10`, `-1.91` CSAT). **100.00% (`62/62`) of 3-handoff** and **75.55% (`173/229`) of 2+ handoff** tickets are `Insufficient info` or `Config issue` returned to L1 (**0** `Fixed` bugs hit 3 handoffs).
- **Category & Duplicate Concentration:** Top 2 — `Roster / booking not syncing` (`344`, `23.82%`, `17` open, `50.87%` esc, `97` avoidable) + `Live tracking / GPS incorrect` (`228`, `15.79%`, `13` open, `55.70%` esc, `67` avoidable) = **39.61%** volume (`572`), **62.50%** open (`30/48`), **62.14%** escalations (`302/486`), **59.64%** avoidable (`164/275`), and **65.40%** `Fixed` bugs (`138/211`). Meanwhile **486/486** escalations got unique `eng_ticket_id`s (**0** reused); duplicates surged **+237.50%** (`8 → 21 → 27`), with #3 `Report export failing` (`206` tickets) driving **30/56 (53.57%)** of all duplicates.

---

## Slide 3: Busting the Team's Myths

| Stakeholder Narrative (`1.pdf`) | Verdict | Hard Evidence from the Data |
|---|---|---|
| **Meera (Support Lead):** *"The real problem is engineering... Some agents close in a few hours... Give us more people."* | **Wrong on Cause & Fast-Closer Myth** | Eng wait is real (`6.90x`), **but** her "fast closer" **Karan B** (`7.87h` med 1st-close; `6.43h` non-esc vs peers `22.05h`) has a **29.49% reopen rate** (`64/217` all; `28.37%` closed) — **4.16x** peers (`7.09%`), causing **42.38%** of company reopens, **worst CSAT (`3.13` vs `3.81`)**, **most open tickets (`9`)**, and `2,641.50h` of closed rework. |
| **Sandeep (Eng Manager):** *"A lot of escalations shouldn't come to eng... Engineers spend hours figuring out the problem."* | **Largely Validated (1 Eng Gap)** | **56.58%** (`275/486`) are non-bugs. **Rahul T** (`151` tickets, `10.46%` vol) escalates **61.59%** (`93/151`, **2.03x** peers' `30.39%`), **75.27%** (`70/93`) avoidable (**25.45%** of total waste), and causes **18/24 (75.00%)** of all `Not a bug - how-to` escalations (`+25` Config, `+18` Insufficient info). *Eng gap:* **0** shared known-issue IDs and `64.83h` med turnaround on real bugs. |
| **Ritika (Head of Ops):** *"No blame game... bring open tickets down this quarter... no budget for new hires."* | **Right to Refuse Headcount** | The **6 baseline peers** (excl. Karan B & Rahul T) hit **6.97% reopen** (`<8%`), **63.95% True FCR**, and **3.84 CSAT**. Yet they still suffer **51.12%** avoidable escalations (`183/358`, `66.55%` of total waste) from missing runbooks/gates — proving we need **both** a workflow tool **and** coaching, not hires. |

| Cohort / Agent | Tickets | Open | Esc % | Avoidable % of Esc | Med 1st-Close | Reopen % (All) | True FCR (Closed) | CSAT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Karan B** *(Premature Closer)* | 217 | **9** | 16.13% | 62.86% | **7.87h** | **29.49%** | 62.98% | **3.13** |
| **Rahul T** *(Over-Escalator)* | 151 | 6 | **61.59%** | **75.27%** | 43.25h | 7.95% | **37.24%** | 3.52 |
| **Baseline 6 Peers** | 1,076 | 33 | 33.27% | 51.12% | 20.47h | **6.97%** | **63.95%** | **3.84** |
| **Company Total (All 8)** | **1,444** | **48** | **33.66%** | **56.58%** | **18.64h** | **10.46%** | **61.03%** | **3.70** |

---

## Slide 4: Defining Success

"Better" means **resolving non-bugs cleanly at L1**, **blocking unverified escalations**, and **preventing premature closures**.

| Type | Metric & Exact Definition | Baseline | 4-Week Target | Owner & Cadence |
|---|---|---:|---:|---|
| **North Star 1** | **True First-Contact Resolution (True FCR):** Closed, `escalated_to_eng == No`, `reopen_count == 0` | **61.03%** (`852/1,396` cl; `59.00%` all) | **>= 70.0%** | **Meera** (Weekly Mon) |
| **North Star 2** | **Avoidable Escalation Rate:** `%` of escalated tickets ending in 5 non-Fixed outcomes | **56.58%** (`275/486`; `55.97%` cl) | **<= 39.45%** (`50%` cut) | **Meera + Sandeep** (Weekly Mon) |
| **Guardrail** | **Reopen Rate `< 8.0%`:** `%` of assigned tickets reopened *(blocks Karan B-style gaming)* | **10.46%** all (`10.17%` cl; 6 peers `6.97%`) | **< 8.0%** (team & per agent) | **Meera** (Weekly 1:1) |
| **Output KPI** | **Open Backlog** & **Client CSAT** | **48** open \| **3.70** CSAT | **<= 37–39** open \| **>= 4.00** | **Ritika** (Weekly Ops Pulse) |

- **Why `< 8%` Reopen Guardrail is essential:** Reopened tickets add **45.28h** mean rework and drop CSAT by **-1.49** (`3.84 → 2.35`).
- **Cadence:** (1) **Daily 5-min L1 Standup** (Meera, Tab 1) clearing `Stale (>48h)` & `Ping-Pong (>=2 handoffs)` tickets; (2) **Monday 10:00 AM IST Ops Pulse** (Ritika, Meera, Sandeep, Tab 3) reviewing True FCR, Avoidable %, Agent Quadrant, and duplicate clusters.

---

## Slide 5: The v0 Solution — RideOps Triage & Escalation Gatekeeper

**Primary User: L1 Support Agent** *(secondary weekly Ops/Coaching view for Meera & Ritika)*.
- **Why L1 Agent?** Every ticket starts at L1, **56.58%** of escalations shouldn't cross into Engineering, and **60.42%** (`29/48`) of open tickets sit with L1. Gating upstream stops backlog creation at the source.

**Working Build (`app.py`, Streamlit + Plotly + Pandas + pure-NumPy TF-IDF; zero hardcoded stats):**

| Feature in `app.py` | Live Functionality on `rideops_support_tickets.csv` | Metric Moved |
|---|---|---|
| **Tab 1: Live Open Queue** | Urgency-ranked queue (`0–100`: Priority + Tier + Age vs Sep 30 + Handoffs + Reopen) with **Ping-Pong Risk (`>=2`)** & **Stale (`>48h`)** badges, inline Duplicate Radar preview, and 1-click handoff to Tab 2. | Open backlog age & P1 SLA |
| **Tab 2A: Duplicate Radar** (`src/duplicate_radar.py`) | Pure-NumPy TF-IDF cosine similarity (unigrams/bigrams + numeric/shift normalization) over all **486** `ENG-xxxx` tickets, returning match %, past verdict & pattern avoidable share. | Cuts `Duplicate` (`56`, `0` reused IDs) |
| **Tab 2B: Category Runbooks** (`src/runbooks.py`) | Dynamic L1 fixes, mandatory preflight checks & diagnostic inputs for **all 10 categories** (e.g., Roster cutoff/sync/API error; GPS app version/permissions/Trip ID/last ping). | Cuts `Config` (`84`), `Insufficient info` (`89`), `How-to` (`24`) |
| **Tab 2C–D: Hard Gate + Closure Guardrail** | **"Generate Engineering Escalation Ticket" stays disabled** until all checks & fields pass, emitting a copy-ready Brief. **"Resolve at L1"** enforces 3 **Closure Quality Checks** + summary and updates live session KPIs. | **True FCR ↑**, **Avoidable ↓**, **Reopen `< 8%`** |
| **Tab 3: Ops Pulse & Simulator** (`src/charts.py`) | 4 dynamic Plotly charts (Volume vs Backlog, Escalation Waste, Ping-Pong Tax, Agent Speed-vs-Reopen Quadrant), Karan B / Rahul T callouts, and live **What-If Impact Simulator**. | Weekly alignment (Meera/Ritika) |

---

## Slide 6: Projected Impact & Assumptions

Numbers match `analysis/metrics_summary.json` (`what_if_baseline`) and `app.py` Tab 3's **What-If Impact Simulator**:

| Scenario (Avoidable / Reopen Cut) | Eng Tickets Deflected (Sep/mo \| Qtr) | Elapsed Queue Hrs Saved (Sep/mo) | Active Eng+L1 Hrs Saved (/mo \| /qtr) | New Avoidable % (from `56.58%`) | Open Backlog: Steady-State (`L=λW`, from `48`) | Open Backlog: Direct Snapshot (from `48`) |
|---|---:|---:|---:|---:|---:|---:|
| **Conservative (`40%` / `0%`)** | `44.4` \| `110.0` | `4,282.8h` (`-7.23h` wait) | `105.6h` \| `316.8h` | `43.88%` *(Esc `26.04%`)* | **42.1** (`-5.9`, `-12.39%`) | **39.2** (`-8.8`, `-18.33%`) |
| **Target (`50%` / `30%`, Default)** | **`55.5` \| `137.5`** | **`6,277.2h`** (`-10.60h` wait) | **`132.0h` \| `396.0h`** | **`39.45%`** *(Esc `24.13%`)* | **39.3** (`-8.7`, **`-18.16%`**) | **37.0** (`-11.0`, **`-22.92%`**) |
| **Stretch (`65%` / `40%`)** | `72.2` \| `178.8` | `8,191.2h` (`-13.84h` wait) | `171.6h` \| `514.8h` | `31.33%` *(Esc `21.28%`)* | **36.6** (`-11.4`, `-23.70%`) | **33.7** (`-14.3`, `-29.79%`) |

- **Exact Formulas:** (1) Excess elapsed time/avoidable = `116.42h − 19.96h` = **`96.46h`** (`24,404.42h` on 253 closed; `26,526.54h` on all 275); reopen extra = **`45.28h`** (`142` closed reopens). (2) Little's Law `ΔL = λ × ΔW` at Sep rate `λ = 592/720h = 0.8222/hr` with `ΔW = (111/592 × avoid_cut × 96.46h) + (68/592 × reopen_cut × 45.28h)`. (3) Direct snapshot = `22` open avoidable × `avoid_cut`. (4) Active Eng+L1 hours = `275 × 1.92` avg handoffs × `avoid_cut × 1.5h` (`÷3` monthly).
- **Explicit Assumptions:** (1) Sep demand (`592/mo`) holds as Q4 run-rate with `$0` hiring; (2) deflected tickets close at L1 mean (`19.96h`); (3) active triage effort = `1.5h/handoff` (adjustable `0.5–4.0h` in app); (4) conservative floor — excludes faster fixes on valid bugs (`64.83h` med) once Eng queue lightens; (5) timestamps anchor to `2026-09-30 23:59:59 IST`.

---

## Slide 7: 4-Week Execution Roadmap

| Week | Key Rollout Actions | Owner(s) | Exit Gate |
|---|---|---|---|
| **W1** | **Gatekeeper Pilot + Targeted Coaching:** Mandate Tab 2 Gatekeeper for Top 2 (`Roster` + `GPS` = `62.50%` open). Coach **Karan B** (`<8%` reopen guardrail + closure checks) & **Rahul T** (shadow **Vikram S** [`68.24%` FCR, `4.55%` reopen] & **Neha P** [`3.94` CSAT] + drill `18` how-to topics). Clear `3` open P1s (`SUP-11258` first) & `25` stale tickets. | Meera + FDE | `100%` Roster/GPS gated; `0` P1s `>48h`; coaching live |
| **W2** | **Duplicate Auto-Linking + Roster/GPS Runbooks:** Create Master Known-Issue `ENG` Parent IDs starting with `Report export failing` (`30/56 = 53.57%` of duplicates: `Monthly trip report download stuck` [`9`], `Scheduled report email not received` [`9`], `Exported report missing <N> trips` [`7`]). Roll out all 10 runbooks + hourly data sync into Radar. | Meera + Sandeep + FDE | Duplicates cut `>=50%`; all 10 categories live |
| **W3** | **SLA & Client Status Visibility:** Automate `24h/48h` alerts for `Stale (>48h)` & `Ping-Pong (>=2)` tickets + 1-click **Client Status macro** (ending Meera's update chases). Proactive outreach to high-pain Enterprise accounts (`Orion Systems` [CSAT `2.43`, `75.00%` esc], `Horizon Infotech` [`28.00%` reopen], `Orion Financial` [`3` open]). | Ritika + Meera | Zero silent escalations `>48h`; Enterprise check-ins done |
| **W4** | **Engineering Bug-Fix Sprint on Top 2 Categories:** Reinvest reclaimed Eng capacity (`~132.0` active hrs/mo) into top `Fixed` bug templates in **Roster** (`78` Fixed — e.g., `Cancelled bookings still appearing`, `20` Fixed) & **GPS** (`60` Fixed — e.g., `ETA showing wrong`, `15` Fixed), tackling **65.40%** (`138/211`) of valid bugs. Week-4 Ops Review. | Sandeep + Ritika | Top Roster/GPS bugs patched; FCR `>=70%`, Avoidable `<=39.45%`, Reopen `<8%` |

---

## Slide 8: Trade-offs — What We Will Deliberately NOT Do

| Deliberately Excluded Now | Why It's Tempting | FDE Rationale for Saying No (Next 4 Weeks) |
|---|---|---|
| **1. No New Hires (L1 or Eng)** | Meera asked for headcount to match `+51.79%` volume growth. | Violates Ritika's `$0` budget *and* scales an ungated funnel (`56.58%` avoidable waste; `1` agent causing `42.38%` of reopens). Revisit only after True FCR `>70%`. |
| **2. No Full Ticketing / CRM Migration** | Moving off email/WhatsApp/portal to a new suite feels clean. | Multi-quarter procurement and retraining delay won't cut Q4 backlog. A sidecar Gatekeeper (`app.py`) enforces intake hygiene on Day 1 over existing channels. |
| **3. No Customer-Facing AI Chatbot Yet** | Promises automated ticket deflection across `191` clients. | Automating replies before fixing `138` Roster/GPS bugs and undocumented runbooks risks hallucinations and higher reopens (`-1.49` CSAT hit). Fix L1 hygiene first. |
| **4. No Complex ML / Fine-Tuned LLM Classifier** | Sounds sophisticated for auto-triaging ticket text. | All `1,444` tickets collapse into **`44` normalized templates** (`201` raw descriptions). Pure-NumPy TF-IDF + deterministic preflight gates solve duplicate & missing-info waste with zero GPU cost and `100%` auditability. |
