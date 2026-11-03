"""A toy culture for the cl-sdk simulator, used to test the closed loop before touching real cells.

The SDK's default random source fires spontaneously but ignores stimulation, so a closed loop
run on it cannot tell a working pipeline from a broken one. This source adds evoked spikes:

- local:  each pulse makes nearby electrodes (within 1.5 electrode pitches) fire 2-10 ms later;
- wiring: optional fixed source->target channel links that fire 5-20 ms later. Wiring the left
          rays to the right motor region (and vice versa) turns the agent into a Braitenberg
          obstacle-avoider, which is the positive control for the whole encode/decode chain.

Firing probability scales with pulse amplitude. There is no plasticity: this is a test
fixture for the plumbing, not a model of learning. Evoked spikes appear in the spike stream
only, not in the raw samples.
"""
import heapq
import threading

import numpy as np
from cl.sim import DataSourceBatch, DataSourceSpike, DataSourceStim
from cl.sim._data_source import RandomDataSource

import config as C

FPS = 25_000
SPIKE_SHAPE = (-60 * np.exp(-0.5 * ((np.arange(75) - 25) / 3) ** 2)).astype(np.float32)


class ToyCulture(RandomDataSource):
    def __init__(self, seed: int, wiring: dict[str, list[int]], p_local: float = 0.4, p_wired: float = 0.5):
        super().__init__(random_seed=seed)
        rows, cols = np.arange(64) % 8, np.arange(64) // 8
        pitch = np.hypot(rows[:, None] - rows[None, :], cols[:, None] - cols[None, :])
        usable = np.array([c not in C.UNUSABLE for c in range(64)])
        self.neighbours = [np.flatnonzero((pitch[c] > 0) & (pitch[c] <= 1.5) & usable) for c in range(64)]
        self.wiring = {int(k): np.array(v, int) for k, v in wiring.items()}
        self.p_local, self.p_wired = p_local, p_wired
        self.rng = np.random.default_rng(seed)
        self.pending: list[tuple[int, int]] = []      # heap of (timestamp, channel)
        self.lock = threading.Lock()

    def on_stim(self, stim: DataSourceStim) -> None:
        gain = max(abs(i) for i in stim.phase_currents_uA)    # 1 uA -> nominal probability
        events = []
        for targets, p, lat_ms in ((self.neighbours[stim.channel], self.p_local, (2, 10)),
                                   (self.wiring.get(stim.channel, np.array([], int)), self.p_wired, (5, 20))):
            fire = targets[self.rng.random(len(targets)) < min(1.0, p * gain)]
            latency = self.rng.uniform(*lat_ms, size=len(fire)) * FPS / 1000
            events += [(stim.timestamp + int(l), int(ch)) for ch, l in zip(fire, latency)]
        with self.lock:
            for event in events:
                heapq.heappush(self.pending, event)

    def read(self, from_timestamp: int, frame_count: int) -> DataSourceBatch:
        batch = super().read(from_timestamp, frame_count)
        end, evoked = from_timestamp + frame_count, []
        with self.lock:
            while self.pending and self.pending[0][0] < end:
                ts, ch = heapq.heappop(self.pending)
                # A response scheduled before this read window was already passed by the read
                # head; deliver it at the start of the window rather than dropping it.
                evoked.append(DataSourceSpike(timestamp=max(ts, from_timestamp), channel=ch,
                                              samples=SPIKE_SHAPE, channel_mean_sample=0.0))
        return DataSourceBatch(frames=batch.frames, spikes=sorted([*batch.spikes, *evoked], key=lambda s: s.timestamp))


def make(seed: int, wiring: dict[str, list[int]]) -> ToyCulture:
    return ToyCulture(seed=seed, wiring=wiring)


def avoider_wiring(mirror: bool) -> dict[str, list[int]]:
    """Left rays excite the right motor region and vice versa, so the agent turns away from walls.
    Built against the *decoded* layout, so with --mirror the avoider still avoids."""
    left_motor, right_motor = (C.MOTOR_RIGHT, C.MOTOR_LEFT) if mirror else (C.MOTOR_LEFT, C.MOTOR_RIGHT)
    return {str(ch): (right_motor if k < 4 else left_motor) for k, ch in enumerate(C.SENSORY)}


def configure(toy: str | None, mirror: bool, seed: int) -> None:
    """Select the simulator's data source: None -> the SDK default, 'local' or 'avoider' -> toy culture."""
    import cl.sim
    if toy is None:
        cl.sim.clear_simulator_data_source()
        return
    assert toy in ("local", "avoider"), f"unknown toy culture {toy!r}"
    wiring = avoider_wiring(mirror) if toy == "avoider" else {}
    cl.sim.set_simulator_data_source("culture:make", config={"seed": seed, "wiring": wiring})
