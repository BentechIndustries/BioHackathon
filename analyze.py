"""Summarise one or more navigation recordings: outcomes, learning within a session,
differences between conditions, and whether stimulation reaches the motor electrodes.

    python analyze.py recordings/*.h5 --out figures
"""
import argparse
from itertools import combinations
from pathlib import Path

import cl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import mannwhitneyu, spearmanr

import config as C
from world import Scene

FPS = 25_000
PSTH_MS = np.arange(-20, 31)                         # 1 ms bins around each sensory pulse


def load(path: Path) -> dict:
    with cl.RecordingView(str(path)) as rec:
        app = dict(rec.attributes["application"])
        events = list(rec.data_streams["events"].values())
        nav = list(rec.data_streams["nav"].values())
        spikes, stims = rec.spikes[:], rec.stims[:]
    label = app["condition"] + (f"+{app['toy']}" if app["toy"] else "") + ("+mirror" if app["mirror"] else "")
    return {"path": path, "label": label, "app": app, "episodes": episodes(events), "nav": nav,
            "spikes": spikes, "stims": stims}


def episodes(events: list[dict]) -> list[dict]:
    """One row per finished episode (the episode cut off by the end of the session is dropped)."""
    rows, start = [], None
    for e in events:
        if e["event"] == "start":
            start = e
        elif e["event"] in ("goal", "collision", "timeout"):
            rows.append({"episode": e["episode"], "outcome": e["event"], "duration": e["duration"],
                         "progress": e["progress"], "t": start["t"]})
    return rows


def steering_coupling(rec: dict) -> float:
    """Correlation between 'obstacles are closer on the left than on the right' and the decoded
    turn rate, over all ticks of play. Negative: the agent turns away from obstacles; positive:
    it turns towards them; ~0: motor output ignores the sensory input."""
    play = [d for d in rec["nav"] if d["state"] == "play"]
    closeness = 1.0 - np.clip(np.array([d["rays"] for d in play]) / C.RAY_MAX_RANGE, 0, 1)
    left_minus_right = closeness[:, :4].sum(axis=1) - closeness[:, 4:].sum(axis=1)
    return float(np.corrcoef(left_minus_right, [d["turn"] for d in play])[0, 1])


def motor_psth(rec: dict) -> np.ndarray:
    """Mean firing rate (Hz per motor electrode) of the motor regions around each sensory pulse.
    A peak 0-2 ms after the pulse is a stimulation artifact; a later peak is an evoked response
    travelling through the culture; a flat line means the motor regions do not see the pulses."""
    motor = rec["app"]["motor_left"] + rec["app"]["motor_right"]
    spike_ts = np.sort(rec["spikes"]["timestamp"][np.isin(rec["spikes"]["channel"], motor)].astype(np.int64))
    stim_ts = np.unique(rec["stims"]["timestamp"][np.isin(rec["stims"]["channel"], C.SENSORY)].astype(np.int64))
    edges = (PSTH_MS * FPS) // 1000
    counts = np.array([np.searchsorted(spike_ts, stim_ts + e).sum() for e in edges])
    return np.diff(counts) / (max(len(stim_ts), 1) * len(motor) * 1e-3)


def summarise(rec: dict) -> dict:
    eps = rec["episodes"]
    assert len(eps) >= 3, f"{rec['path']}: only {len(eps)} finished episodes, too few to analyse"
    progress = np.array([e["progress"] for e in eps])
    outcome = np.array([e["outcome"] for e in eps])
    third = max(len(eps) // 3, 1)
    rho, p_rho = spearmanr(np.arange(len(eps)), progress)
    p_late = mannwhitneyu(progress[-third:], progress[:third], alternative="greater").pvalue
    return {"label": rec["label"], "n": len(eps), "goal": (outcome == "goal").mean(),
            "collision": (outcome == "collision").mean(), "timeout": (outcome == "timeout").mean(),
            "progress": progress.mean(), "first": progress[:third].mean(), "last": progress[-third:].mean(),
            "rho": rho, "p_rho": p_rho, "p_late": p_late, "coupling": steering_coupling(rec)}


def plot(recs: list[dict], scene: Scene, out: Path) -> None:
    extent = [scene.origin[0], scene.origin[0] + scene.occ.shape[1] * scene.res,
              scene.origin[1], scene.origin[1] + scene.occ.shape[0] * scene.res]
    background = np.where(scene.occ, 0.0, np.where(scene.free, 1.0, 0.8))
    fig, axes = plt.subplots(3, len(recs), figsize=(4.2 * len(recs), 11), squeeze=False)
    for col, rec in enumerate(recs):
        ax = axes[0, col]
        ax.imshow(background, origin="lower", cmap="gray", vmin=0, vmax=1, extent=extent)
        n_eps = max(len(rec["episodes"]), 1)
        nav = [d for d in rec["nav"] if d["state"] == "play"]
        ep = np.array([d["ep"] for d in nav])
        xz = np.array([[d["x"], d["z"]] for d in nav])
        for k in np.unique(ep):
            sel = ep == k
            ax.plot(xz[sel, 0], xz[sel, 1], lw=0.7, color=plt.cm.viridis(min(k / n_eps, 1.0)), alpha=0.8)
        ax.plot(*scene.goal, "*", color="gold", mec="k", ms=14)
        ax.set_title(f"{rec['label']}\n{rec['path'].name[:19]}", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])

        ax = axes[1, col]
        progress = np.array([e["progress"] for e in rec["episodes"]])
        colors = {"goal": "tab:green", "collision": "tab:red", "timeout": "tab:gray"}
        for outcome, color in colors.items():
            idx = [i for i, e in enumerate(rec["episodes"]) if e["outcome"] == outcome]
            ax.scatter(idx, progress[idx], s=12, color=color, label=outcome)
        if len(progress) >= 5:
            ax.plot(np.arange(len(progress)), np.convolve(progress, np.ones(5) / 5, mode="same"), color="k", lw=1)
        ax.set(xlabel="episode (colour on map above)", ylabel="progress towards goal", ylim=(-0.3, 1.05))
        ax.legend(fontsize=7, loc="lower right")

        ax = axes[2, col]
        ax.step(PSTH_MS[:-1], motor_psth(rec), where="post", color="tab:purple")
        ax.axvline(0, color="k", lw=0.5)
        ax.set(xlabel="ms from sensory pulse", ylabel="motor firing rate (Hz/electrode)")
    fig.tight_layout()
    fig.savefig(out / "sessions.png", dpi=130)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("recordings", type=Path, nargs="+")
    parser.add_argument("--scene", type=Path, default=Path("scene/livingroom.npz"))
    parser.add_argument("--out", type=Path, default=Path("figures"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    recs = [load(p) for p in sorted(args.recordings)]
    rows = [summarise(r) for r in recs]
    header = f"{'session':28s} {'n':>4s} {'goal':>5s} {'coll':>5s} {'tout':>5s} {'prog':>5s} " \
             f"{'first':>6s} {'last':>5s} {'rho':>6s} {'p_rho':>6s} {'p_late':>6s} {'couple':>6s}"
    print(header)
    for r in rows:
        print(f"{r['label']:28s} {r['n']:4d} {r['goal']:5.2f} {r['collision']:5.2f} {r['timeout']:5.2f} "
              f"{r['progress']:5.2f} {r['first']:6.2f} {r['last']:5.2f} {r['rho']:6.2f} {r['p_rho']:6.3f} "
              f"{r['p_late']:6.3f} {r['coupling']:+6.2f}")

    groups: dict[str, list[float]] = {}
    for rec in recs:
        groups.setdefault(rec["label"], []).extend(e["progress"] for e in rec["episodes"])
    if len(groups) > 1:
        print("\nprogress per episode, two-sided Mann-Whitney U between groups (episodes pooled across sessions):")
        for a, b in combinations(groups, 2):
            p = mannwhitneyu(groups[a], groups[b]).pvalue
            print(f"  {a:>24s} ({np.mean(groups[a]):.2f}) vs {b:<24s} ({np.mean(groups[b]):.2f})  p = {p:.3g}")

    plot(recs, Scene.load(args.scene), args.out)
    print(f"\nfigure: {args.out / 'sessions.png'}")


if __name__ == "__main__":
    main()
