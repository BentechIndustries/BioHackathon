"""Closed-loop navigation session: the culture steers an agent through the living room.

    python run.py --condition feedback --minutes 20            # on the CL1
    CL_SDK_ACCELERATED_TIME=1 python run.py --toy avoider      # simulator positive control

Conditions (after Kagan et al. 2022):
    feedback  sensory stimulation, predictable feedback on progress/goal, unpredictable on collision
    silent    sensory stimulation, feedback periods replaced by equally long silent pauses
    rest      no stimulation at all; spontaneous activity alone steers the agent
"""
import argparse
from pathlib import Path

import cl
import numpy as np

import config as C
from world import Agent, Scene

CONDITIONS = ("feedback", "silent", "rest")
DT = 1.0 / C.TICK_HZ
SENSORY_PULSE = cl.StimDesign(C.PULSE_US, -C.SENSORY_UA, C.PULSE_US, C.SENSORY_UA)
PREDICTABLE_PULSE = cl.StimDesign(C.PULSE_US, -C.PREDICTABLE_UA, C.PULSE_US, C.PREDICTABLE_UA)
UNPREDICTABLE_PULSE = cl.StimDesign(C.PULSE_US, -C.UNPREDICTABLE_UA, C.PULSE_US, C.UNPREDICTABLE_UA)
PREDICTABLE_BURST = cl.BurstDesign(C.PREDICTABLE_PULSES, C.PREDICTABLE_HZ)
PREDICTABLE_S = C.PREDICTABLE_PULSES / C.PREDICTABLE_HZ


class Encoder:
    """Ray distance -> pulse rate on that ray's electrode, via one phase accumulator per ray."""

    def __init__(self, rng: np.random.Generator):
        self.phase = rng.random(len(C.SENSORY))          # random phases so rays do not fire in lockstep

    def due(self, rays: np.ndarray) -> list[int]:
        closeness = 1.0 - np.clip(rays / C.RAY_MAX_RANGE, 0.0, 1.0)
        self.phase += (C.FREQ_MIN_HZ + (C.FREQ_MAX_HZ - C.FREQ_MIN_HZ) * closeness) * DT
        fire = self.phase >= 1.0
        self.phase[fire] -= 1.0
        return [C.SENSORY[i] for i in np.flatnonzero(fire)]


class Decoder:
    """Spike counts in the two motor regions -> turn rate (positive = counter-clockwise = left).
    Each region's rate is divided by its own slow baseline, so a region that is simply more active
    does not bias the agent. The turn then depends on the lateralisation index of those relative
    rates, which is unchanged when both regions speed up together (e.g. when sensory stimulation
    starts after calibration): a plain difference would saturate until the baselines caught up,
    and that slow recovery looks exactly like within-session learning."""

    def __init__(self, mirror: bool):
        self.left, self.right = (C.MOTOR_RIGHT, C.MOTOR_LEFT) if mirror else (C.MOTOR_LEFT, C.MOTOR_RIGHT)
        self.region = np.full(64, -1)
        self.region[self.left], self.region[self.right] = 0, 1
        self.rate = np.zeros(2)
        self.baseline = np.zeros(2)

    def update(self, spikes: list) -> None:
        region = self.region[[s.channel for s in spikes]] if spikes else np.empty(0, int)
        counts = np.array([(region == 0).sum(), (region == 1).sum()])
        self.rate += DT / C.RATE_TAU_S * (counts / DT - self.rate)
        self.baseline += DT / C.BASELINE_TAU_S * (self.rate - self.baseline)

    def turn(self) -> float:
        relative = self.rate / self.baseline
        total = relative.sum()
        index = (relative[0] - relative[1]) / total if total > 0 else 0.0
        return float(C.TURN_MAX * np.tanh(C.TURN_GAIN * index))


class Session:
    def __init__(self, neurons, scene: Scene, condition: str, mirror: bool, rng: np.random.Generator):
        self.neurons, self.scene, self.condition, self.rng = neurons, scene, condition, rng
        self.agent, self.encoder, self.decoder = Agent(scene, rng), Encoder(rng), Decoder(mirror)
        self.state, self.resume_at, self.reset_after, self.punishing = "calibrate", C.CALIBRATION_S, True, False
        self.episode, self.episode_start = -1, 0.0
        self.counts = {"goal": 0, "collision": 0, "timeout": 0}
        grid = np.where(scene.occ, "#", np.where(scene.free, ".", " "))
        self.nav = neurons.create_data_stream("nav", attributes={
            "map": ["".join(row) for row in grid], "origin": scene.origin.tolist(), "res": scene.res,
            "goal": scene.goal.tolist(), "goal_radius": C.GOAL_RADIUS, "condition": condition,
            "ray_angles": C.RAY_ANGLES.tolist(), "ray_max": C.RAY_MAX_RANGE, "sensory": C.SENSORY,
            "motor": [self.decoder.left, self.decoder.right], "episode": 0, "counts": dict(self.counts)})
        self.events = neurons.create_data_stream("events")

    def tick(self, tick) -> None:
        t = tick.iteration * DT
        self.decoder.update(tick.analysis.spikes)
        stimulated: list[int] = []

        if self.state == "calibrate" and t >= self.resume_at:
            assert (self.decoder.baseline > 0).all(), \
                f"a motor region was silent during calibration (baseline {self.decoder.baseline}); check the layout"
            self.start_episode(tick, t)

        elif self.state == "pause":
            if self.punishing and self.rng.random() < C.UNPREDICTABLE_HZ * DT:
                stimulated = [int(self.rng.choice(C.SENSORY))]
                self.neurons.stim(stimulated[0], UNPREDICTABLE_PULSE)
            if t >= self.resume_at:
                self.punishing = False
                if self.reset_after:
                    self.start_episode(tick, t)
                else:
                    self.state = "play"

        elif self.state == "play":
            event = self.agent.step(self.decoder.turn(), DT)
            if event is None and t - self.episode_start >= C.EPISODE_MAX_S:
                event = "timeout"
            if event is None and self.agent.best_dist - self.scene.geodesic(self.agent.x, self.agent.z) >= C.MILESTONE_M:
                self.agent.best_dist -= C.MILESTONE_M
                event = "milestone"
            if event is not None:
                stimulated = self.handle(event, tick, t)
            elif self.condition != "rest":
                stimulated = self.encoder.due(self.rays())
                if stimulated:
                    self.neurons.stim(cl.ChannelSet(*stimulated), SENSORY_PULSE)

        self.nav.append(tick.iteration_timestamp, {
            "t": round(t, 3), "ep": self.episode, "state": self.state, "x": round(self.agent.x, 4),
            "z": round(self.agent.z, 4), "h": round(self.agent.heading, 4), "turn": round(self.decoder.turn(), 4)
            if self.state != "calibrate" else 0.0, "rate": self.decoder.rate.round(2).tolist(),
            "rays": self.rays().round(3).tolist(), "stim": stimulated})

    def rays(self) -> np.ndarray:
        return self.scene.rays(self.agent.x, self.agent.z, self.agent.heading)

    def handle(self, event: str, tick, t: float) -> list[int]:
        """Deliver the feedback for an event and schedule the pause that follows it."""
        give_feedback = self.condition == "feedback"
        stimulated: list[int] = []
        if event in ("milestone", "goal"):
            if give_feedback:
                stimulated = list(C.SENSORY)
                self.neurons.stim(cl.ChannelSet(*C.SENSORY), PREDICTABLE_PULSE, PREDICTABLE_BURST)
            pause = PREDICTABLE_S
        elif event == "collision":
            self.punishing = give_feedback
            pause = C.UNPREDICTABLE_S
        else:                                            # timeout: no feedback, restart straight away
            pause = DT
        self.state, self.resume_at, self.reset_after = "pause", t + pause, event != "milestone"
        self.log(tick, event)
        if event != "milestone":
            self.counts[event] += 1
            self.nav.set_attribute("counts", dict(self.counts))
            print(f"[{t:7.1f}s] episode {self.episode:3d} {event:9s} progress {self.agent.progress:+.2f} "
                  f"after {t - self.episode_start:4.1f}s   totals {self.counts}")
        return stimulated

    def start_episode(self, tick, t: float) -> None:
        self.agent.reset()
        self.episode += 1
        self.state, self.episode_start = "play", t
        self.nav.set_attribute("episode", self.episode)
        self.log(tick, "start")

    def log(self, tick, event: str) -> None:
        self.events.append(tick.iteration_timestamp, {
            "event": event, "episode": self.episode, "t": round(tick.iteration * DT, 3),
            "duration": round(tick.iteration * DT - self.episode_start, 3), "progress": round(self.agent.progress, 4),
            "dist": round(self.scene.geodesic(self.agent.x, self.agent.z), 4)})


def run_session(scene_path: Path, condition: str, minutes: float, mirror: bool, seed: int,
                out_dir: Path, toy: str | None = None, live_view: bool = False) -> Path:
    """Run one session and return the path of its recording. `live_view` shows the visualiser
    in Jupyter; it is created here, after the simulator is configured, so it attaches to the
    right data source and websocket."""
    assert condition in CONDITIONS, f"unknown condition {condition!r}"
    scene, rng = Scene.load(scene_path), np.random.default_rng(seed)
    if cl.is_simulator():
        import culture
        culture.configure(toy, mirror, seed)
    else:
        assert toy is None, "--toy only makes sense in the cl-sdk simulator"
    out_dir.mkdir(parents=True, exist_ok=True)
    with cl.open() as neurons:
        recording = neurons.record(
            file_location=str(out_dir.resolve()), file_suffix=f"nav_{condition}{'_mirror' if mirror else ''}",
            attributes={"condition": condition, "mirror": mirror, "seed": seed, "toy": toy or "",
                        "minutes": minutes, "tick_hz": C.TICK_HZ, "sensory": C.SENSORY,
                        "motor_left": C.MOTOR_LEFT, "motor_right": C.MOTOR_RIGHT})
        session = Session(neurons, scene, condition, mirror, rng)
        if live_view:
            from cl.visualisation.jupyter import display_visualiser
            here = Path(__file__).parent / "visualiser"
            display_visualiser(javascript_file=here / "nav.mjs", html_file=here / "nav.html", data_streams=["nav"])
        for tick in neurons.loop(C.TICK_HZ, stop_after_seconds=C.CALIBRATION_S + 60 * minutes):
            session.tick(tick)
        recording.stop()
    print(f"recording: {recording.file['path']}")
    return Path(recording.file["path"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--condition", choices=CONDITIONS, default="feedback")
    parser.add_argument("--minutes", type=float, default=20.0)
    parser.add_argument("--mirror", action="store_true", help="swap the left and right motor regions")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--scene", type=Path, default=Path("scene/livingroom.npz"))
    parser.add_argument("--out", type=Path, default=Path("recordings"))
    parser.add_argument("--toy", choices=("local", "avoider"),
                        help="simulator only: toy culture with local evoked responses, optionally wired as an obstacle avoider")
    args = parser.parse_args()
    run_session(args.scene, args.condition, args.minutes, args.mirror, args.seed, args.out, args.toy)


if __name__ == "__main__":
    main()
