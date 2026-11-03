import random

import cl
from cl import ChannelSet, StimDesign

from .cube import Cube, move_name, sequence_text

def visible_mix_seconds(scramble_turns):
    return scramble_turns + 1

TICKS_PER_SECOND = 10
TICKS_PER_BEAT = 10
MOVE_CHANNELS = (
    (8, 9, 10, 11),
    (12, 13, 14, 15),
    (16, 17, 18, 19),
    (20, 21, 22, 23),
    (24, 25, 26, 27),
    (28, 29, 30, 31),
    (32, 33, 34, 35),
    (36, 37, 38, 39),
    (40, 41, 42, 43),
    (44, 45, 46, 47),
    (48, 49, 50, 51),
    (52, 53, 54, 55),
)
_CHANNEL_MOVE = {}
for _move, _channels in enumerate(MOVE_CHANNELS):
    for _channel in _channels:
        _CHANNEL_MOVE[_channel] = _move

_REWARD = StimDesign(160, -1.0, 160, 1.0)


def play(duration_s, scramble_turns, seed=None):
    rng = random.Random(seed)
    cube = Cube()
    scramble = []
    last_face = None
    for _ in range(scramble_turns):
        choices = [move for move in range(12) if move // 2 != last_face]
        move = rng.choice(choices)
        scramble.append(move)
        last_face = move // 2
    accepted = []
    mix_beats = 1 + len(scramble)
    listen_ticks = int(duration_s * TICKS_PER_SECOND)
    with cl.open() as neurons:
        stream = neurons.create_data_stream("cube")
        stamp = -1

        def publish(when, move_label, phase):
            nonlocal stamp
            when = int(when)
            if when <= stamp:
                when = stamp + 1
            stamp = when
            stream.append(
                stamp,
                {
                    "facelets": list(cube.facelets),
                    "move": move_label,
                    "solved": cube.solved() and phase == "Solved",
                    "turns": len(accepted),
                    "label": phase,
                },
            )

        mixed = None
        remaining = []
        next_mix_tick = TICKS_PER_BEAT
        mixes_sent = 0
        solving = False
        for tick in neurons.loop(
            ticks_per_second=TICKS_PER_SECOND,
            stop_after_ticks=mix_beats * TICKS_PER_BEAT + listen_ticks,
            ignore_jitter=True,
        ):
            if tick.iteration == 0:
                publish(tick.iteration_next_timestamp, "", "Ready")
            if not solving:
                if tick.iteration < next_mix_tick:
                    continue
                if mixes_sent < len(scramble):
                    move = scramble[mixes_sent]
                    cube.apply(move)
                    mixes_sent += 1
                    next_mix_tick = tick.iteration + TICKS_PER_BEAT
                    publish(tick.iteration_next_timestamp, move_name(move), "Mixing")
                    continue
                mixed = cube.net()
                remaining = cube.solution()
                solving = True
            if not remaining:
                tick.loop.stop()
                break
            counts = [0] * 12
            for spike in tick.analysis.spikes:
                move = _CHANNEL_MOVE.get(spike.channel)
                if move is not None:
                    counts[move] += 1
            top = max(counts)
            if top <= 0:
                continue
            winners = [move for move, count in enumerate(counts) if count == top]
            if len(winners) != 1 or winners[0] != remaining[0]:
                continue
            chosen = winners[0]
            cube.apply(chosen)
            accepted.append(chosen)
            remaining = remaining[1:]
            phase = "Solved" if not remaining else "Solving"
            publish(tick.iteration_next_timestamp, move_name(chosen), phase)
            neurons.stim(ChannelSet(*MOVE_CHANNELS[chosen]), _REWARD)
            if not remaining:
                tick.loop.stop()
                break
        if mixed is None:
            mixed = cube.net()
    solved = cube.solved()
    outcome = "Solved." if solved else "Time ran out before it was solved."
    text = "\n".join(
        [
            outcome,
            "",
            "Scramble:",
            sequence_text(scramble),
            "",
            "Mixed cube:",
            mixed,
            "",
            "Turns taken from the dish:",
            sequence_text(accepted),
            "",
            "Cube now:",
            cube.net(),
        ]
    )
    return solved, text
