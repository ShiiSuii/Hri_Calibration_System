"""
plot_results.py — ICCAS Study Paper Figure Generator
======================================================
Usage:
    python plot_results.py logs/subj01_condB_scen2_20250506_143000.csv

Generates 6 publication-ready figures:
    1. System state vs time (step plot)
    2. MediaPipe attention vs time (pitch, yaw + is_looking boolean)
    3. VLM attention labels vs time (categorical)
    4. Audio events vs time (markers for start, pause, resume, close)
    5. Actuators vs time (neck_pitch, upper_eyelids, jaw_position)
    6. Latency: state-transition events scatter plot
"""

import sys
import os
import json
import argparse

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MaxNLocator

# ── Colour map for states ──────────────────────────────────────────────────
STATE_COLORS = {
    "sleeping":           "#546E7A",
    "person_detected":    "#1565C0",
    "attention_detected": "#00838F",
    "interacting":        "#2E7D32",
    "user_distracted":    "#BF360C",
    "waiting":            "#E65100",
    "resume_interaction": "#558B2F",
    "finished":           "#880E4F",
}
STATE_ORDER = list(STATE_COLORS.keys())

AUDIO_MARKERS = {
    "apertura":     ("▶ apertura",     "#42A5F5", "^"),
    "disponibilidad": ("▶ disponibilidad", "#26C6DA", "^"),
    "respuesta":    ("▶ respuesta",    "#66BB6A", "^"),
    "pausa":        ("⏸ pausa",        "#FFA726", "v"),
    "reanudacion":  ("↺ reanudacion",  "#9CCC65", "^"),
    "cierre":       ("▶ cierre",       "#AB47BC", "^"),
    "despedida":    ("◼ despedida",    "#EF5350", "v"),
    "desengagement":("◼ desengagement","#B71C1C", "v"),
}


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["elapsed_s"] = df["elapsed_time_ms"] / 1000.0

    # Booleans
    for col in ("mediapipe_face_detected", "mediapipe_is_looking",
                "state_transition", "vlm_person_present"):
        if col in df.columns:
            df[col] = df[col].map(
                lambda v: str(v).strip().lower() in ("true", "1", "yes")
            )

    # Numeric
    for col in ("mediapipe_pitch", "mediapipe_yaw",
                "neck_pitch", "neck_pan", "upper_eyelids", "lower_eyelids", "jaw_position"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def figure1_state_vs_time(df: pd.DataFrame, ax: plt.Axes, title_prefix: str):
    """Step plot of system state over time."""
    state_map = {s: i for i, s in enumerate(STATE_ORDER)}
    df["state_num"] = df["current_state"].map(lambda s: state_map.get(s, -1))

    ax.step(df["elapsed_s"], df["state_num"], where="post",
            color="#4FC3F7", linewidth=1.5, alpha=0.9)

    # Colour fill per state
    for state, color in STATE_COLORS.items():
        mask = df["current_state"] == state
        if mask.any():
            ax.fill_between(
                df["elapsed_s"], df["state_num"],
                where=mask, step="post",
                color=color, alpha=0.35, label=state
            )

    ax.set_yticks(range(len(STATE_ORDER)))
    ax.set_yticklabels([s.replace("_", "\n") for s in STATE_ORDER], fontsize=7)
    ax.set_xlabel("Time (s)")
    ax.set_title(f"{title_prefix} — Fig 1: System State vs Time")
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    patches = [mpatches.Patch(color=c, label=s) for s, c in STATE_COLORS.items()]
    ax.legend(handles=patches, loc="upper right", fontsize=7, ncol=2)


def figure2_attention_vs_time(df: pd.DataFrame, ax1: plt.Axes):
    """Pitch, yaw and is_looking boolean over time."""
    ax2 = ax1.twinx()

    ax1.plot(df["elapsed_s"], df["mediapipe_pitch"],
             color="#42A5F5", linewidth=1, label="Pitch", alpha=0.8)
    ax1.plot(df["elapsed_s"], df["mediapipe_yaw"],
             color="#EF5350", linewidth=1, label="Yaw",   alpha=0.8)
    ax1.axhline(-30, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax1.axhline(+30, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax1.set_ylabel("Degrees", color="#ccc")
    ax1.set_xlabel("Time (s)")
    ax1.legend(loc="upper left", fontsize=8)

    # is_looking as filled area
    ax2.fill_between(df["elapsed_s"], df["mediapipe_is_looking"].astype(int),
                     color="#66BB6A", alpha=0.25, label="Is looking", step="post")
    ax2.set_ylim(-0.1, 1.5)
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["No", "Yes"], fontsize=8)
    ax2.set_ylabel("Looking at robot", color="#66BB6A")
    ax2.legend(loc="upper right", fontsize=8)

    ax1.set_title("Fig 2: MediaPipe Attention vs Time")
    ax1.grid(linestyle="--", alpha=0.3)


def figure3_vlm_vs_time(df: pd.DataFrame, ax: plt.Axes):
    """VLM attention_target as categorical scatter."""
    VLM_LABELS = ["robot", "phone", "elsewhere", "none", "unknown"]
    label_map  = {l: i for i, l in enumerate(VLM_LABELS)}
    VLM_COLORS = {"robot": "#66BB6A", "phone": "#EF5350", "elsewhere": "#FFA726",
                  "none": "#78909C", "unknown": "#9E9E9E"}

    if "vlm_attention_target" not in df.columns:
        ax.text(0.5, 0.5, "No VLM data", ha="center", va="center",
                transform=ax.transAxes)
        return

    # Plot transitions as step blocks
    prev_label, prev_t = None, 0
    for _, row in df.iterrows():
        lbl = row.get("vlm_attention_target", "unknown")
        t   = row["elapsed_s"]
        if lbl != prev_label:
            if prev_label is not None:
                ax.axhspan(
                    label_map.get(prev_label, 0) - 0.4,
                    label_map.get(prev_label, 0) + 0.4,
                    xmin=prev_t / df["elapsed_s"].max(),
                    xmax=t     / df["elapsed_s"].max(),
                    color=VLM_COLORS.get(prev_label, "#aaa"),
                    alpha=0.4,
                )
            prev_label, prev_t = lbl, t

    ax.scatter(
        df["elapsed_s"],
        df["vlm_attention_target"].map(lambda l: label_map.get(l, 4)),
        c=[VLM_COLORS.get(l, "#aaa") for l in df["vlm_attention_target"]],
        s=8, alpha=0.7,
    )
    ax.set_yticks(range(len(VLM_LABELS)))
    ax.set_yticklabels(VLM_LABELS, fontsize=8)
    ax.set_xlabel("Time (s)")
    ax.set_title("Fig 3: VLM Attention Target vs Time")
    ax.grid(linestyle="--", alpha=0.3)


def figure4_audio_events(df: pd.DataFrame, ax: plt.Axes):
    """Audio state as coloured bands + event markers."""
    if "audio_state" not in df.columns:
        return

    # Reconstruct audio track from audio_state column
    playing_mask = df["audio_state"].str.startswith("playing")
    paused_mask  = df["audio_state"].str.startswith("paused")
    idle_mask    = df["audio_state"] == "idle"

    ax.fill_between(df["elapsed_s"], playing_mask.astype(float),
                    color="#66BB6A", alpha=0.25, label="Playing", step="post")
    ax.fill_between(df["elapsed_s"], paused_mask.astype(float),
                    color="#FFA726", alpha=0.25, label="Paused",  step="post")

    # Mark state transitions involving audio
    transitions = df[df["state_transition"] == True]
    for _, row in transitions.iterrows():
        note = str(row.get("event_note", ""))
        t    = row["elapsed_s"]
        if "audio" in note.lower() or row.get("audio_state", "idle") != "idle":
            ax.axvline(t, color="#42A5F5", linewidth=0.8, alpha=0.6)

    ax.set_ylim(-0.1, 1.3)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Off", "Active"], fontsize=8)
    ax.set_xlabel("Time (s)")
    ax.set_title("Fig 4: Audio Activity vs Time")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(linestyle="--", alpha=0.3)


def figure5_actuators_vs_time(df: pd.DataFrame, ax: plt.Axes):
    """Neck pitch, upper eyelids and jaw position over time."""
    cols = {
        "neck_pitch":    ("#42A5F5", "Neck Pitch (ch18)"),
        "upper_eyelids": ("#AB47BC", "Upper Eyelids"),
        "jaw_position":  ("#EF5350", "Jaw (ch0)"),
    }
    for col, (color, label) in cols.items():
        if col in df.columns:
            ax.plot(df["elapsed_s"], df[col],
                    color=color, linewidth=1, label=label, alpha=0.85)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Servo pulse (μs)")
    ax.set_title("Fig 5: Actuators vs Time")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(linestyle="--", alpha=0.3)


def figure6_latency(df: pd.DataFrame, ax: plt.Axes):
    """Scatter of state-transition events with elapsed time."""
    transitions = df[df["state_transition"] == True].copy()
    if transitions.empty:
        ax.text(0.5, 0.5, "No transitions recorded", ha="center", va="center",
                transform=ax.transAxes)
        return

    state_map = {s: i for i, s in enumerate(STATE_ORDER)}
    transitions["state_num"] = transitions["current_state"].map(
        lambda s: state_map.get(s, -1)
    )

    scatter_colors = [
        STATE_COLORS.get(s, "#aaa") for s in transitions["current_state"]
    ]
    ax.scatter(transitions["elapsed_s"], transitions["state_num"],
               c=scatter_colors, s=60, zorder=5, alpha=0.9)

    for _, row in transitions.iterrows():
        ax.annotate(
            row["current_state"].replace("_", "\n"),
            (row["elapsed_s"], row["state_num"]),
            textcoords="offset points", xytext=(4, 4),
            fontsize=6, alpha=0.7,
        )

    ax.set_yticks(range(len(STATE_ORDER)))
    ax.set_yticklabels([s.replace("_", "\n") for s in STATE_ORDER], fontsize=7)
    ax.set_xlabel("Time (s)")
    ax.set_title("Fig 6: State Transition Events (Latency Proxy)")
    ax.grid(linestyle="--", alpha=0.3)


def generate_all_figures(csv_path: str, output_dir: str | None = None):
    print(f"[Plot] Loading {csv_path}")
    df = load_csv(csv_path)

    # Read subject metadata from first row
    meta_cond  = df["condition"].iloc[0]  if "condition"  in df.columns else "?"
    meta_subj  = df["participant_id"].iloc[0] if "participant_id" in df.columns else "?"
    meta_scen  = df["scenario"].iloc[0]   if "scenario"   in df.columns else "?"
    title_pfx  = f"Subj {meta_subj} | Cond {meta_cond} | Scen {meta_scen}"

    fig = plt.figure(figsize=(18, 22), facecolor="#111318")
    gs  = GridSpec(6, 1, figure=fig, hspace=0.55)

    axes = [fig.add_subplot(gs[i]) for i in range(6)]
    for ax in axes:
        ax.set_facecolor("#1A1E2A")
        ax.tick_params(colors="#ccc", labelsize=8)
        ax.xaxis.label.set_color("#ccc")
        ax.yaxis.label.set_color("#ccc")
        ax.title.set_color("#E8ECF4")
        for spine in ax.spines.values():
            spine.set_edgecolor("#2A2F3E")

    figure1_state_vs_time(df, axes[0], title_pfx)
    figure2_attention_vs_time(df, axes[1])
    figure3_vlm_vs_time(df, axes[2])
    figure4_audio_events(df, axes[3])
    figure5_actuators_vs_time(df, axes[4])
    figure6_latency(df, axes[5])

    fig.suptitle(f"ICCAS HRI Study — {title_pfx}", fontsize=14,
                 color="#E8ECF4", y=0.995)

    if output_dir is None:
        output_dir = os.path.dirname(csv_path)

    base = os.path.splitext(os.path.basename(csv_path))[0]
    out  = os.path.join(output_dir, f"{base}_figures.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"[Plot] Saved → {out}")
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ICCAS Paper Figure Generator")
    parser.add_argument("csv", help="Path to trial CSV log file")
    parser.add_argument("--out", default=None, help="Output directory (default: same as CSV)")
    args = parser.parse_args()

    generate_all_figures(args.csv, args.out)
