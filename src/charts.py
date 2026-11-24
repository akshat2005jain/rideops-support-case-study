"""Executive Plotly visualizations for Tab 3 (Ops Pulse & Coaching View).

Clean light/slate aesthetic, zero chart clutter, direct labels, and
every datapoint driven dynamically from computed DataFrames.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PALETTE = {
    "navy": "#0F172A",
    "slate": "#475569",
    "muted": "#94A3B8",
    "grid": "#E2E8F0",
    "blue": "#0284C7",
    "sky": "#38BDF8",
    "teal": "#0D9488",
    "green": "#059669",
    "amber": "#D97706",
    "coral": "#DC2626",
    "soft_red": "#EF4444",
    "soft_blue": "#CBD5E1",
}

BASE_LAYOUT = dict(
    font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", color=PALETTE["navy"], size=12),
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    margin=dict(l=24, r=24, t=48, b=32),
    hoverlabel=dict(bgcolor="#0F172A", font_color="#FFFFFF", font_size=12),
)


def make_monthly_volume_backlog_chart(monthly_df: pd.DataFrame) -> go.Figure:
    """Stacked bar of Monthly Tickets (L1 vs Valid Esc vs Avoidable Esc) + EOM Open Backlog line."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            name="L1 Resolved (Non-Escalated)",
            x=monthly_df["month_label"],
            y=monthly_df["non_escalated"],
            marker_color="#CBD5E1",
            text=monthly_df["non_escalated"],
            textposition="inside",
            textfont=dict(color=PALETTE["navy"], size=11),
            hovertemplate="%{x}<br>Non-Escalated: %{y}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            name="Escalated — Valid Bug (Fixed)",
            x=monthly_df["month_label"],
            y=monthly_df["escalated_fixed"],
            marker_color=PALETTE["blue"],
            text=monthly_df["escalated_fixed"],
            textposition="inside",
            textfont=dict(color="#FFFFFF", size=11),
            hovertemplate="%{x}<br>Valid Bug (Fixed): %{y}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            name="Escalated — Avoidable Waste",
            x=monthly_df["month_label"],
            y=monthly_df["escalated_avoidable"],
            marker_color=PALETTE["coral"],
            text=monthly_df["escalated_avoidable"],
            textposition="inside",
            textfont=dict(color="#FFFFFF", size=11),
            hovertemplate="%{x}<br>Avoidable Escalations: %{y}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            name="End-of-Month Open Backlog",
            x=monthly_df["month_label"],
            y=monthly_df["open_eom_total"],
            mode="lines+markers",
            line=dict(color=PALETTE["navy"], width=3),
            marker=dict(size=10, color=PALETTE["amber"], line=dict(color=PALETTE["navy"], width=2)),
            hovertemplate="%{x}<br>Open Backlog (EOM): %{y} tickets<extra></extra>",
        ),
        secondary_y=True,
    )

    max_vol = int(monthly_df["total_tickets"].max()) if len(monthly_df) else 600
    max_open = int(monthly_df["open_eom_total"].max()) if len(monthly_df) else 60

    # Place crisp pill labels above each EOM open point on secondary y-axis
    for _, row in monthly_df.iterrows():
        fig.add_annotation(
            x=row["month_label"],
            y=row["open_eom_total"],
            yref="y2",
            text=f"<b>{int(row['open_eom_total'])} open</b>",
            showarrow=False,
            yshift=17,
            font=dict(color=PALETTE["navy"], size=11),
            bgcolor="rgba(255, 255, 255, 0.94)",
            bordercolor="#CBD5E1",
            borderwidth=1,
            borderpad=3,
        )

    # Non-negative tick values for right y-axis while reserving upper band above bars
    tick_step = max(10, int(round(max_open / 3.0 / 5.0) * 5))
    right_ticks = list(range(0, max_open + tick_step + 1, tick_step))

    layout_cfg = {**BASE_LAYOUT, "margin": dict(l=24, r=24, t=92, b=36)}
    fig.update_layout(
        **layout_cfg,
        barmode="stack",
        title=dict(
            text="Monthly Volume Growth, Escalation Split & EOM Open Backlog",
            font=dict(size=14),
            y=0.97,
            yanchor="top",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=10.5),
        ),
        height=395,
    )
    fig.update_xaxes(showgrid=False, linecolor=PALETTE["grid"])
    fig.update_yaxes(
        title_text="Monthly Tickets Created",
        range=[0, max_vol * 1.52],
        gridcolor=PALETTE["grid"],
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Open Tickets (End of Month)",
        range=[-max_open * 1.15, max_open * 1.32],
        tickmode="array",
        tickvals=right_ticks,
        showgrid=False,
        secondary_y=True,
    )
    return fig


def make_escalation_waste_chart(waste_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart breaking down Avoidable Escalation categories vs Fixed."""
    df_plot = waste_df.sort_values(by="count", ascending=True).copy()
    colors = [
        PALETTE["green"] if not is_av else (PALETTE["coral"] if idx >= len(df_plot) - 3 else PALETTE["amber"])
        for idx, is_av in enumerate(df_plot["is_avoidable"])
    ]

    fig = go.Figure(
        go.Bar(
            x=df_plot["count"],
            y=df_plot["eng_outcome"],
            orientation="h",
            marker_color=colors,
            text=[f"{c} ({p:.1f}%)" for c, p in zip(df_plot["count"], df_plot["share_pct"])],
            textposition="outside",
            textfont=dict(size=11, color=PALETTE["navy"]),
            customdata=df_plot[["bucket", "median_close_hrs"]].to_numpy(),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Type: %{customdata[0]}<br>"
                "Tickets: %{x}<br>"
                "Median Close: %{customdata[1]}h<extra></extra>"
            ),
        )
    )

    max_x = int(df_plot["count"].max()) if len(df_plot) else 250
    total_cnt = float(waste_df["count"].sum()) if len(waste_df) else 0.0
    avoid_pct = (
        float(waste_df.loc[waste_df["is_avoidable"], "count"].sum()) / total_cnt * 100.0
        if total_cnt > 0
        else 0.0
    )
    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(
            text=f"Escalation Outcome Breakdown ({avoid_pct:.1f}% Avoidable vs Fixed)",
            font=dict(size=14),
        ),
        xaxis=dict(title="Escalated Tickets", range=[0, max_x * 1.28], gridcolor=PALETTE["grid"]),
        yaxis=dict(title="", showgrid=False),
        height=370,
        showlegend=False,
    )
    return fig


def make_handoff_penalty_chart(handoff_df: pd.DataFrame) -> go.Figure:
    """Bar chart showing exponential resolution time penalty by engineering handoff count."""
    colors = [PALETTE["green"], PALETTE["blue"], PALETTE["amber"], PALETTE["coral"]][: len(handoff_df)]

    fig = go.Figure(
        go.Bar(
            x=handoff_df["handoff_bucket"],
            y=handoff_df["median_hrs"],
            marker_color=colors,
            width=0.55,
            text=[
                f"<b>{h:.1f}h</b><br>({m:.1f}x)" if m > 1.0 else f"<b>{h:.1f}h</b><br>(Baseline)"
                for h, m in zip(handoff_df["median_hrs"], handoff_df["multiple_vs_l1"])
            ],
            textposition="outside",
            textfont=dict(size=11, color=PALETTE["navy"]),
            customdata=handoff_df[["closed_tickets", "mean_hrs"]].to_numpy(),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Median Resolution: %{y:.1f} hrs<br>"
                "Mean Resolution: %{customdata[1]:.1f} hrs<br>"
                "Closed Tickets: %{customdata[0]}<extra></extra>"
            ),
        )
    )

    max_y = float(handoff_df["median_hrs"].max()) if len(handoff_df) else 180.0
    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text="The Ping-Pong Tax: Median Resolution Hours by Eng Handoffs", font=dict(size=14)),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="Median Final Resolution (Hours)", range=[0, max_y * 1.26], gridcolor=PALETTE["grid"]),
        height=370,
        showlegend=False,
    )
    return fig


def make_agent_quadrant_chart(agent_df: pd.DataFrame) -> go.Figure:
    """Agent Quality vs Speed Quadrant: Median First-Close Time vs Reopen Rate,
    encoding Escalation Rate via color and Volume via marker size.
    """
    med_speed = float(agent_df["median_first_close_hrs"].median()) if len(agent_df) else 20.0
    guardrail_reopen = 8.0

    max_x = float(agent_df["median_first_close_hrs"].max()) * 1.18 if len(agent_df) else 50.0
    max_y = float(agent_df["reopen_rate_pct"].max()) * 1.22 if len(agent_df) else 35.0

    # Pixel-offset callout positions per agent so dense center-cluster labels never overlap
    label_offsets: dict[str, tuple[int, int]] = {
        "Karan B": (42, 0),
        "Neha P": (-40, -24),
        "Priya D": (34, -22),
        "Arjun K": (-52, 8),
        "Vikram S": (-38, 22),
        "Ananya R": (44, -14),
        "Sneha M": (40, 20),
        "Rahul T": (0, -24),
    }

    fig = go.Figure()

    # Subtle danger-zone shading for Premature Closures (Fast Close + Reopen >= 8%)
    fig.add_shape(
        type="rect",
        x0=0,
        x1=med_speed,
        y0=guardrail_reopen,
        y1=max_y,
        fillcolor="rgba(220, 38, 38, 0.06)",
        line_width=0,
        layer="below",
    )
    # Subtle healthy-zone shading (Reopen < 8% & below high speed threshold)
    fig.add_shape(
        type="rect",
        x0=0,
        x1=med_speed * 1.35,
        y0=0,
        y1=guardrail_reopen,
        fillcolor="rgba(5, 150, 105, 0.06)",
        line_width=0,
        layer="below",
    )

    # Quadrant reference lines (guardrail label anchored left, cleanly clear of Rahul T)
    fig.add_vline(
        x=med_speed,
        line_dash="dot",
        line_color=PALETTE["muted"],
        annotation_text=f"Team Median Close ({med_speed:.1f}h)",
        annotation_position="top right",
        annotation_font=dict(size=10, color=PALETTE["slate"]),
    )
    fig.add_hline(
        y=guardrail_reopen,
        line_dash="dash",
        line_color=PALETTE["coral"],
        annotation_text="Reopen Guardrail (8%)",
        annotation_position="top left",
        annotation_font=dict(size=10, color=PALETTE["coral"]),
    )

    fig.add_trace(
        go.Scatter(
            x=agent_df["median_first_close_hrs"],
            y=agent_df["reopen_rate_pct"],
            mode="markers",
            text=agent_df["assigned_agent"],
            marker=dict(
                size=agent_df["total_tickets"] / 8.5,
                sizemode="diameter",
                color=agent_df["escalation_rate_pct"],
                colorscale=[[0.0, "#059669"], [0.45, "#0284C7"], [0.75, "#D97706"], [1.0, "#DC2626"]],
                showscale=True,
                colorbar=dict(title="Esc. Rate %", thickness=12, len=0.75),
                line=dict(color=PALETTE["navy"], width=1.4),
            ),
            customdata=agent_df[
                [
                    "total_tickets",
                    "escalation_rate_pct",
                    "avoidable_of_esc_pct",
                    "mean_csat",
                    "how_to_esc_count",
                    "coaching_flag",
                ]
            ].to_numpy(),
            hovertemplate=(
                "<b>%{text}</b> (%{customdata[5]})<br>"
                "Median First-Close: %{x:.1f} hrs<br>"
                "Reopen Rate: %{y:.1f}%<br>"
                "Escalation Rate: %{customdata[1]:.1f}% (Avoidable: %{customdata[2]:.1f}%)<br>"
                "Not-a-Bug/How-To Esc: %{customdata[4]}<br>"
                "Tickets: %{customdata[0]} | Avg CSAT: %{customdata[3]:.2f}<extra></extra>"
            ),
        )
    )

    # Non-overlapping direct labels with subtle hairline leader where needed
    for _, row in agent_df.iterrows():
        name = str(row["assigned_agent"])
        ax, ay = label_offsets.get(name, (26, -16))
        is_callout = name in ("Karan B", "Rahul T")
        fig.add_annotation(
            x=float(row["median_first_close_hrs"]),
            y=float(row["reopen_rate_pct"]),
            text=f"<b>{name}</b>" if is_callout else name,
            showarrow=True,
            arrowhead=0,
            arrowwidth=1,
            arrowcolor="#CBD5E1",
            ax=ax,
            ay=ay,
            font=dict(size=10.5, color=PALETTE["navy"]),
            bgcolor="rgba(255, 255, 255, 0.86)",
            borderpad=2,
        )

    # Quadrant corner annotations
    fig.add_annotation(
        x=med_speed * 0.45,
        y=max_y * 0.92,
        text="DANGER: Fast & Premature Closures",
        showarrow=False,
        font=dict(size=10, color=PALETTE["coral"]),
    )
    fig.add_annotation(
        x=max_x * 0.78,
        y=guardrail_reopen * 0.35,
        text="Slow / High-Escalation Zone",
        showarrow=False,
        font=dict(size=10, color=PALETTE["amber"]),
    )

    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(
            text="Agent Quality vs Speed Quadrant (Color = Escalation %, Size = Volume)",
            font=dict(size=14),
        ),
        xaxis=dict(title="Median First-Close Time (Hours)", range=[0, max_x], gridcolor=PALETTE["grid"]),
        yaxis=dict(title="Reopen Rate (% of All Assigned Tickets)", range=[0, max_y], gridcolor=PALETTE["grid"]),
        height=400,
        showlegend=False,
    )
    return fig
