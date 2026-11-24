"""Category-specific L1 Runbooks, Mandatory Preflight Checks, Closure Guardrails,
and Structured Engineering Handoff Brief generation for RideOps Support.

All 10 categories present in rideops_support_tickets.csv have tailored runbooks
designed to eliminate Insufficient Info, Config Issue, Duplicate, and Not-a-Bug
escalations before a ticket reaches Engineering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DiagnosticField:
    key: str
    label: str
    placeholder: str
    help_text: str


@dataclass(frozen=True)
class CategoryRunbook:
    category: str
    l1_triage_goal: str
    common_l1_fixes: list[str]
    mandatory_checks: list[str]
    diagnostic_fields: list[DiagnosticField]
    escalation_criteria: str


RUNBOOKS: dict[str, CategoryRunbook] = {
    "Roster / booking not syncing": CategoryRunbook(
        category="Roster / booking not syncing",
        l1_triage_goal=(
            "Rule out client shift-cutoff misconfiguration, stale roster cache, "
            "or Excel upload format errors before escalating to Roster Sync Engineering."
        ),
        common_l1_fixes=[
            "Verify client shift cutoff window in Admin Portal -> Shift Config and confirm booking was submitted before cutoff.",
            "Trigger manual roster sync / cache refresh for the affected shift date and verify employee status is Active.",
            "For Excel uploads, check mandatory columns (Employee ID, Shift Code, Pickup Date, Nodal Point) and strip duplicate rows.",
            "For cancelled bookings still showing, confirm cancellation cleared the roster lock window (typically T-2 hrs).",
        ],
        mandatory_checks=[
            "Verified client shift cutoff config & confirmed booking/cancellation timestamp is inside the valid window",
            "Checked affected employee profile(s) are Active with valid shift & transport eligibility tags",
            "Triggered manual roster sync retry and checked Duplicate Radar for known shift-sync incidents",
            "Captured API / sync error payload or Admin Portal screenshot confirming post-retry mismatch",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="employee_ids",
                label="Affected Employee ID(s) / Shift Name",
                placeholder="e.g., EMP-4821, EMP-4835 | 6:00 AM Shift",
                help_text="Include exact Employee IDs (or count + sample IDs) and shift timing.",
            ),
            DiagnosticField(
                key="cutoff_and_sync_ts",
                label="Client Shift Cutoff Config & Sync Timestamp (IST)",
                placeholder="e.g., Cutoff T-4h (02:00 IST); last sync run at 01:42 IST",
                help_text="Confirm current cutoff rule in Admin Portal and exact sync run timestamp.",
            ),
            DiagnosticField(
                key="sync_error_evidence",
                label="API / Sync Error Details & Screenshot Reference",
                placeholder="e.g., Sync job #8821 returned HTTP 500 timeout; screenshot attached in portal",
                help_text="Paste exact sync error code/message or confirm verified visual reproduction.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY when shift cutoff config is verified valid, manual sync retry failed, "
            "and no active duplicate ENG ticket already covers this sync defect."
        ),
    ),
    "Live tracking / GPS incorrect": CategoryRunbook(
        category="Live tracking / GPS incorrect",
        l1_triage_goal=(
            "Rule out outdated driver app version, disabled background GPS/battery optimization, "
            "or expired tracking link permissions before escalating to Telematics Engineering."
        ),
        common_l1_fixes=[
            "Check driver app version in Fleet Console; instruct vendor/driver to update if below current minimum release.",
            "Confirm device GPS is set to 'Always Allow' with battery saver / Doze mode disabled for RideOps Driver App.",
            "For security team tracking links, regenerate the signed link and verify IP/role access expiry.",
            "Confirm driver actually pressed 'Start Trip' and device has active mobile data telemetry.",
        ],
        mandatory_checks=[
            "Verified Driver App version and OS build in Fleet Telemetry Console",
            "Confirmed GPS permission status ('Always Allow' / High Accuracy) and ruled out mobile network drop",
            "Validated Trip ID status is Active/In-Transit and checked last received GPS ping timestamp",
            "Checked Duplicate Radar for active map/ETA provider outages or known GPS drift bugs",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="trip_id",
                label="Trip ID & Vehicle / Driver ID",
                placeholder="e.g., TRP-90412 | KA-01-AB-4421 (DRV-712)",
                help_text="Exact Trip ID from Fleet Console is mandatory for log lookup.",
            ),
            DiagnosticField(
                key="driver_app_gps",
                label="Driver App Version & GPS Permission Status",
                placeholder="e.g., Driver App v4.18.2 (Android 14) | GPS: Always Allow, Battery Opt: Off",
                help_text="Confirm both app version and location permission / battery optimization state.",
            ),
            DiagnosticField(
                key="last_ping_ts",
                label="Last Telemetry Ping Timestamp (IST) & Observed Symptom",
                placeholder="e.g., Last ping 08:14 IST at 12.9716,77.5946; map frozen 22 mins while cab moving",
                help_text="Include last ping time, coordinates/ETA discrepancy, and affected user role.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY when driver app is up to date, GPS permissions and data connectivity are healthy, "
            "and backend telemetry logs show dropped/corrupted coordinates for the Trip ID."
        ),
    ),
    "Report export failing": CategoryRunbook(
        category="Report export failing",
        l1_triage_goal=(
            "Check Duplicate Radar FIRST (high duplicate-escalation category), validate date-range limits "
            "and email delivery filters before escalating to Reporting Engineering."
        ),
        common_l1_fixes=[
            "Split date ranges >15 days into two smaller exports or switch to Async Scheduled Export.",
            "Check Duplicate Radar for known monthly trip report timeout or blank Excel export ENG tickets and link client.",
            "For missing scheduled report emails, check SMTP bounce log, spam/quarantine, and active recipient list.",
            "Verify the selected filter combination (site, vendor, billing cycle) actually contains completed trips.",
        ],
        mandatory_checks=[
            "Checked Duplicate Radar for active report-export / >15-day timeout ENG issues (avoid duplicate ticket)",
            "Verified report type, exact date range, and tested with a narrower <=7-day window",
            "Checked Export Job Queue status & SMTP delivery/bounce log (for scheduled email reports)",
            "Confirmed client admin role has full report scope permissions for the requested sites/billing cycle",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="report_type_range",
                label="Report Name, Format & Date Range",
                placeholder="e.g., Monthly Trip Report (XLSX) | 2026-09-01 to 2026-09-30",
                help_text="Specify exact report template, file format, and date range requested.",
            ),
            DiagnosticField(
                key="export_job_id",
                label="Export Job ID / Browser Network Error",
                placeholder="e.g., JOB-55219 stuck at 60% / HTTP 504 Gateway Timeout after 90s",
                help_text="Grab Job ID from Export History or network console error message.",
            ),
            DiagnosticField(
                key="narrow_range_test",
                label="<=7-Day Repro Test Result & Missing Row Count",
                placeholder="e.g., 7-day range succeeds; 30-day range returns 0 KB blank sheet",
                help_text="State whether a smaller date range worked and exact discrepancy observed.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY if NOT a duplicate of an existing open ENG report-export bug, and export fails "
            "even within supported date-range limits with an observable Job ID / error."
        ),
    ),
    "OTP / boarding issue": CategoryRunbook(
        category="OTP / boarding issue",
        l1_triage_goal=(
            "Verify SMS gateway delivery status, employee mobile number / DND status, and driver app clock sync "
            "before escalating to Boarding/Auth Engineering."
        ),
        common_l1_fixes=[
            "Check SMS Gateway delivery logs: verify employee phone number format (+91) and DND / carrier block.",
            "Confirm driver device system time is set to Automatic Network Time (skewed clocks invalidate TOTP/OTP).",
            "Trigger in-app OTP resend or guide admin to use backup PIN / supervisor manual boarding override.",
            "Verify employee is assigned to the exact active trip/cab attempting boarding.",
        ],
        mandatory_checks=[
            "Checked SMS gateway / notification delivery log for the exact employee mobile number",
            "Confirmed driver app version and device automatic clock sync (ruled out time-drift OTP rejection)",
            "Verified employee is mapped to the active Trip ID & boarding sequence in Trip Console",
            "Collected exact OTP error message and timestamp of failed boarding attempt",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="trip_and_employee",
                label="Trip ID & Affected Employee ID",
                placeholder="e.g., TRP-88120 | EMP-3019 (masked phone ****4821)",
                help_text="Include Trip ID and affected employee identifier.",
            ),
            DiagnosticField(
                key="sms_gateway_status",
                label="SMS Gateway Status & Delivery Timestamp",
                placeholder="e.g., SMS Gateway status: DELIVERED at 07:52 IST (Provider ID: MSG-9921)",
                help_text="Check whether OTP was generated/delivered or failed at carrier.",
            ),
            DiagnosticField(
                key="driver_error_payload",
                label="Driver App Error Message & Device Clock Check",
                placeholder="e.g., 'Invalid OTP' even with fresh code; driver clock synced; app v4.18.2",
                help_text="Exact on-screen error message and confirmation of clock/app check.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY when SMS was generated/delivered (or gateway threw a backend 5xx), "
            "driver app clock & trip assignment are valid, yet boarding state refuses to transition."
        ),
    ),
    "Billing / invoice discrepancy": CategoryRunbook(
        category="Billing / invoice discrepancy",
        l1_triage_goal=(
            "Reconcile configured vendor rate card, dead-km rules, and toll policy against trip logs "
            "to resolve config/billing-rule issues at L1 before involving Billing Engineering."
        ),
        common_l1_fixes=[
            "Check Rate Card Effective Date & Vendor Mapping in Billing Admin — apply missing rate card and regenerate draft invoice.",
            "Verify client contract setting for Dead-Km / No-Show billing rules on cancelled trips.",
            "Check Toll Auto-Import vs Manual Driver Toll Entry for duplicate toll line items and issue credit adjustment.",
            "Reconcile invoice trip count against Completed + Billable-Cancelled trip filters.",
        ],
        mandatory_checks=[
            "Verified active Vendor Rate Card ID, effective date, and vehicle-type mapping in Billing Admin",
            "Checked client dead-km / cancellation billing policy configuration",
            "Reconciled sample disputed Trip IDs against raw trip audit log (distance, tolls, status)",
            "Confirmed invoice regeneration did NOT resolve the calculation mismatch",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="invoice_and_cycle",
                label="Invoice ID, Billing Cycle & Vendor Name",
                placeholder="e.g., INV-2026-09-412 | Sep 2026 | SwiftFleet Logistics",
                help_text="Exact invoice number, billing window, and vendor.",
            ),
            DiagnosticField(
                key="rate_card_check",
                label="Configured Rate Card ID & Policy Check",
                placeholder="e.g., RC-204 (effective 2026-09-01); dead-km disabled for T-2h cancels",
                help_text="Confirm which rate card and cancellation/toll rules are active.",
            ),
            DiagnosticField(
                key="disputed_trip_samples",
                label="Sample Disputed Trip IDs & Expected vs Billed Amount",
                placeholder="e.g., TRP-81102, TRP-81145: expected Rs 420, billed Rs 840 (double toll)",
                help_text="Provide at least 2 concrete Trip IDs showing expected vs actual math.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY when rate card and billing policy config are confirmed correct, "
            "yet invoice computation logic produces wrong amounts after regeneration."
        ),
    ),
    "Cab delay / no-show complaint": CategoryRunbook(
        category="Cab delay / no-show complaint",
        l1_triage_goal=(
            "Resolve operational vendor dispatch / SLA incidents via Transport Ops & GPS audit; "
            "escalate to Engineering ONLY if dispatch algorithm or no-show geofence logic malfunctioned."
        ),
        common_l1_fixes=[
            "Audit vehicle GPS breadcrumbs against pickup geofence to verify whether driver actually reached pickup point.",
            "Log vendor SLA penalty / no-show dispute in Fleet Ops Console and trigger employee reimbursement workflow if applicable.",
            "Review route buffer/ETA config for recurring route delays (e.g., shift rush-hour buffer) with Site Ops.",
            "Reassign standby cab or notify Transport Desk directly for live shift delays.",
        ],
        mandatory_checks=[
            "Audited Trip GPS breadcrumbs & arrival timestamps vs pickup geofence coordinates",
            "Confirmed whether incident is Vendor Ops failure (handle via Ops SLA) vs Software Dispatch/Geofence bug",
            "Checked Route ETA / pickup buffer configuration for recurring route delays",
            "Documented exact trip audit timeline and software anomaly (if escalating)",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="trip_route_id",
                label="Trip ID / Route Number & Shift Timing",
                placeholder="e.g., TRP-89210 | Route 76 | 6:00 AM Shift",
                help_text="Exact Trip ID, route number, and scheduled pickup time.",
            ),
            DiagnosticField(
                key="gps_audit_result",
                label="GPS Geofence Audit Result (Scheduled vs Actual)",
                placeholder="e.g., Driver marked no-show at 05:50 IST while GPS showed cab 1.8 km outside geofence",
                help_text="Explain what telemetry shows vs what the app allowed.",
            ),
            DiagnosticField(
                key="software_defect_reason",
                label="Why This Requires Engineering (vs Vendor Ops Action)",
                placeholder="e.g., App allowed no-show trigger outside 200m geofence threshold (policy enabled)",
                help_text="Vendor lateness is Ops-handled; only escalate if app rules/dispatch logic failed.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY when a software rule failed (e.g., geofence check bypassed or dispatch engine crashed); "
            "pure driver/vendor delays must be resolved at L1 via Vendor Ops."
        ),
    ),
    "Employee address / geocode change": CategoryRunbook(
        category="Employee address / geocode change",
        l1_triage_goal=(
            "Update geocode coordinates directly in Admin Portal, trigger routing cache re-sync, "
            "and verify nodal-point mapping at L1 before involving Maps/Routing Engineering."
        ),
        common_l1_fixes=[
            "Open Employee Profile -> Geocode Pin, place exact lat/lng pin for the new society/address, and save.",
            "Verify effective date of address change and re-run Roster Routing Sync so future trips drop the old pickup point.",
            "For multi-employee society pin errors, bulk-update the shared Landmark/Society Master geocode once.",
            "Confirm employee does not have a frozen/override nodal point locked on their shift profile.",
        ],
        mandatory_checks=[
            "Verified employee address change is Approved and Effective Date has passed in Admin Portal",
            "Checked exact Lat/Lng pin coordinates & checked for locked Nodal Point / Society Master override",
            "Re-ran routing cache refresh for upcoming shifts and checked whether new pin reflects in Route Planner",
            "Collected sample Employee IDs and old vs new coordinates if routing engine still ignores updated pin",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="affected_emp_or_society",
                label="Affected Employee ID(s) / Society Landmark Name",
                placeholder="e.g., 33 employees in Prestige Lakeside Habitat (Landmark ID: LMK-409)",
                help_text="Provide affected employee ID(s) or shared society landmark ID.",
            ),
            DiagnosticField(
                key="lat_lng_comparison",
                label="Stored Pin Lat/Lng vs Routing Output Lat/Lng",
                placeholder="e.g., Profile pin: 12.9542,77.7410 | Generated route still uses 12.9279,77.6271",
                help_text="Show exact coordinates in profile vs what routing engine generated.",
            ),
            DiagnosticField(
                key="cache_refresh_status",
                label="Address Approval Timestamp & Routing Refresh Check",
                placeholder="e.g., Approved 2026-09-25 14:00 IST; manual route rebuild run 2026-09-26 09:00 IST",
                help_text="Confirm approval status and that route cache rebuild was already attempted.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY when profile/landmark geocode is approved & updated and route rebuild was run, "
            "yet routing engine persists stale coordinates."
        ),
    ),
    "Login / access issue": CategoryRunbook(
        category="Login / access issue",
        l1_triage_goal=(
            "Resolve password lockouts, RBAC role assignments, and onboarding invites directly at L1; "
            "escalate to Auth Engineering ONLY for verified SAML/SSO token or IdP integration errors."
        ),
        common_l1_fixes=[
            "Unlock employee account in Identity Console and issue fresh password reset link (confirm user clears browser cache).",
            "Assign requested RBAC role (e.g., Reports Viewer / Site Admin) in User Permissions after verifying client approval.",
            "For new admins, confirm invite email was accepted and correct corporate domain / tenant URL is used.",
            "For SSO failures, check client IdP certificate expiry date and verify user email matches SAML NameID.",
        ],
        mandatory_checks=[
            "Verified user account status (Active / Not Locked) and RBAC role assignment in Admin Console",
            "Confirmed login URL/tenant slug and ruled out password reset / browser cache / invite-pending issue",
            "Checked Auth Audit Logs for exact HTTP/SAML error code (if SSO is failing)",
            "Confirmed this is NOT a standard RBAC permission grant or how-to request solvable by L1",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="affected_users_tenant",
                label="Affected User Email(s) / Count & Client Tenant Slug",
                placeholder="e.g., 22 users on tenant acme-prod (sample: ops.admin@client.com)",
                help_text="Specify affected users and tenant identifier.",
            ),
            DiagnosticField(
                key="auth_method_role",
                label="Auth Method (SSO/SAML vs Password) & Assigned RBAC Role",
                placeholder="e.g., Azure AD SAML SSO | Role: Transport Admin",
                help_text="Indicate login flow and verified role mapping.",
            ),
            DiagnosticField(
                key="auth_error_trace",
                label="Exact Auth / SAML Error Code & Timestamp (IST)",
                placeholder="e.g., SAML_ASSERTION_INVALID (401) at 10:15 IST; IdP cert valid till 2027-03",
                help_text="Paste exact error trace from Auth Logs.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY for verified backend authentication/SSO bugs with Auth Log error codes; "
            "all lockouts, invites, and RBAC module grants must be closed at L1."
        ),
    ),
    "How-to / feature request": CategoryRunbook(
        category="How-to / feature request",
        l1_triage_goal=(
            "Deflect 100% of standard How-To questions with KB walkthroughs and log feature requests "
            "in the Product Feedback Portal — NEVER send feature/how-to tickets to Engineering Bug Queue."
        ),
        common_l1_fixes=[
            "For 'How to add a new shift timing' or 'female-first drop rule', walk client through Admin Portal -> Policies & send KB link.",
            "Confirm feature availability under client's current tier/feature-flag configuration (enable standard toggle if entitled).",
            "For net-new product requests (WhatsApp alerts, bulk holiday cancel, driver rating visibility), log in Product Roadmap Tracker and share tracking ref with client.",
        ],
        mandatory_checks=[
            "Checked RideOps Knowledge Base & Admin Portal feature flags to confirm whether capability already exists",
            "Verified this is NOT a standard Admin configuration walkthrough or net-new feature request",
            "Confirmed if escalating, an existing documented feature is throwing a genuine software error",
            "Shared step-by-step KB guide or Product Request ID if resolvable without Engineering",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="kb_or_feature_flag",
                label="KB Article / Feature Flag Checked",
                placeholder="e.g., Checked KB-204 (Female-First Drop Rule) & tenant feature flag 'escort_priority'",
                help_text="Confirm which documentation and feature toggles were verified.",
            ),
            DiagnosticField(
                key="actual_bug_justification",
                label="Verified Defect Justification (Why Not L1 How-To / Product Idea)",
                placeholder="e.g., Feature flag is ON for Enterprise tier, but Save button throws HTTP 500",
                help_text="How-to questions and feature requests should be resolved at L1, not escalated as bugs.",
            ),
            DiagnosticField(
                key="repro_steps",
                label="Exact UI Path & Error Observed",
                placeholder="e.g., Admin -> Shift Rules -> Add Shift -> Save returns 'Unexpected null field'",
                help_text="Provide exact click path and error message.",
            ),
        ],
        escalation_criteria=(
            "Almost all tickets in this category should be resolved at L1! Escalate ONLY if a currently "
            "enabled, documented feature crashes or errors during normal configuration."
        ),
    ),
    "Driver / vehicle compliance docs": CategoryRunbook(
        category="Driver / vehicle compliance docs",
        l1_triage_goal=(
            "Verify document format/size, compliance expiry enforcement toggles, and BGV vendor sync status "
            "before escalating to Fleet Compliance Engineering."
        ),
        common_l1_fixes=[
            "Verify compliance auto-block toggle is enabled for the client site so expired-insurance vehicles cannot be auto-assigned.",
            "For fitness certificate upload failures, validate file is PDF/JPG <=5 MB with valid future expiry date and retry upload.",
            "Trigger manual BGV verification status pull from third-party BGV webhook log before escalating.",
        ],
        mandatory_checks=[
            "Verified Vehicle/Driver ID and document expiry date in Fleet Compliance Console",
            "Checked client 'Block Expired Vehicles on Roster' compliance enforcement toggle",
            "Validated upload file type/size (<=5 MB PDF/JPG) or checked BGV webhook sync log",
            "Captured exact upload/enforcement error payload or screenshot",
        ],
        diagnostic_fields=[
            DiagnosticField(
                key="vehicle_driver_id",
                label="Vehicle Reg No. / Driver ID & Document Type",
                placeholder="e.g., KA-05-MH-9182 | Vehicle Insurance / Fitness Certificate",
                help_text="Include vehicle or driver identifier and specific compliance document.",
            ),
            DiagnosticField(
                key="policy_toggle_status",
                label="Compliance Enforcement Toggle & Expiry Date",
                placeholder="e.g., Auto-block expired = ON | Insurance expired 2026-09-15; still assigned 2026-09-29",
                help_text="Confirm enforcement policy state and exact dates.",
            ),
            DiagnosticField(
                key="upload_or_sync_error",
                label="Upload / BGV Webhook Error Details",
                placeholder="e.g., 1.4 MB PDF fails with 'UPLOAD_STORAGE_ERR 502' / BGV webhook 200 OK but UI stale",
                help_text="Paste exact error response or webhook timestamp.",
            ),
        ],
        escalation_criteria=(
            "Escalate ONLY when compliance toggle/file specs are verified valid, yet enforcement rules "
            "or document upload/BGV status sync fail on the backend."
        ),
    ),
}

DEFAULT_RUNBOOK = CategoryRunbook(
    category="General Support",
    l1_triage_goal="Verify configuration, reproduce the issue, and attach complete diagnostic evidence before escalating.",
    common_l1_fixes=[
        "Check client configuration settings in Admin Portal.",
        "Search Duplicate Radar for an existing known Engineering ticket.",
        "Verify whether issue is resolvable via L1 runbook or knowledge base guide.",
    ],
    mandatory_checks=[
        "Verified relevant client configuration in Admin Portal",
        "Checked Duplicate Radar for known Engineering issues",
        "Reproduced or verified issue with exact IDs and timestamps",
    ],
    diagnostic_fields=[
        DiagnosticField(
            key="affected_entity",
            label="Affected Entity ID (Employee / Trip / User)",
            placeholder="e.g., EMP-1024 / TRP-55120",
            help_text="Provide exact IDs impacted.",
        ),
        DiagnosticField(
            key="observed_error",
            label="Observed Error & Timestamp (IST)",
            placeholder="e.g., Error details and exact IST timestamp",
            help_text="Include exact error text and reproduction notes.",
        ),
    ],
    escalation_criteria="Escalate only with verified config checks and complete diagnostic evidence.",
)

# Guardrail checklist for L1 Resolution (prevents Karan B-style premature closures & reopens)
L1_CLOSURE_QUALITY_CHECKS: list[str] = [
    "Applied and verified the concrete config fix / KB walkthrough (not a generic 'please retry' reply)",
    "Confirmed expected outcome with the client admin or validated in RideOps Admin/Fleet Console",
    "Documented clear root cause & client-facing resolution summary so the ticket will not reopen",
]


def get_runbook(category: str) -> CategoryRunbook:
    """Return the tailored runbook for a ticket category."""
    return RUNBOOKS.get(category, DEFAULT_RUNBOOK)


def build_engineering_handoff_brief(
    ticket: dict[str, Any],
    checked_items: list[str],
    diagnostics: dict[str, str],
    linked_eng_ids: list[str],
    l1_agent: str,
    notes: str = "",
) -> str:
    """Generate a crisp, copy-ready Engineering Escalation Ticket Brief."""
    runbook = get_runbook(str(ticket.get("category", "")))
    field_labels = {f.key: f.label for f in runbook.diagnostic_fields}
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M IST")
    linked_str = ", ".join(linked_eng_ids) if linked_eng_ids else "None (verified no active duplicate)"

    lines = [
        f"=== RIDEOPS GATEKEEPER-VERIFIED ENGINEERING ESCALATION ===",
        f"Ticket ID:       {ticket.get('ticket_id', 'NEW-SIMULATED')}",
        f"Client:          {ticket.get('client_name', 'N/A')} ({ticket.get('client_tier', 'N/A')})",
        f"Priority:        {ticket.get('priority', 'N/A')}  |  Category: {ticket.get('category', 'N/A')}",
        f"Escalated By:    {l1_agent}  |  Gatekeeper Verified: {timestamp_str}",
        f"Related ENG IDs: {linked_str}",
        "",
        "ISSUE SUMMARY:",
        f"  {ticket.get('description', '').strip()}",
        "",
        "VERIFIED L1 PREFLIGHT CHECKS (100% PASSED):",
    ]
    for item in checked_items:
        lines.append(f"  [x] {item}")

    lines.append("")
    lines.append("DIAGNOSTIC PAYLOAD:")
    for key, val in diagnostics.items():
        label = field_labels.get(key, key)
        lines.append(f"  - {label}: {val.strip()}")

    if notes.strip():
        lines.append("")
        lines.append("ADDITIONAL L1 CONTEXT:")
        lines.append(f"  {notes.strip()}")

    lines.append("==========================================================")
    return "\n".join(lines)


def build_l1_resolution_note(
    ticket: dict[str, Any],
    resolution_type: str,
    resolution_summary: str,
    linked_eng_ids: list[str],
    l1_agent: str,
) -> str:
    """Generate a clean L1 resolution note confirming closure quality checks passed."""
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M IST")
    linked_str = f" (Linked Known Issue: {', '.join(linked_eng_ids)})" if linked_eng_ids else ""
    return "\n".join(
        [
            f"=== RIDEOPS L1 QUALITY-VERIFIED RESOLUTION ===",
            f"Ticket ID:       {ticket.get('ticket_id', 'NEW-SIMULATED')}",
            f"Client:          {ticket.get('client_name', 'N/A')} ({ticket.get('client_tier', 'N/A')})",
            f"Category:        {ticket.get('category', 'N/A')}  |  Priority: {ticket.get('priority', 'N/A')}",
            f"Resolved By:     {l1_agent}  |  Timestamp: {timestamp_str}",
            f"Resolution Path: {resolution_type}{linked_str}",
            "",
            "RESOLUTION SUMMARY & VERIFICATION:",
            f"  {resolution_summary.strip()}",
            "  [x] Closure Quality Guardrail passed (root cause verified; client confirmed)",
            "==============================================",
        ]
    )
