import queue
import random
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cl
from cl import ChannelSet, StimDesign

from .cube import Cube, move_name

TICKS_PER_SECOND = 10
TICKS_PER_BEAT = 10
MIX_TURNS = 6
SENSE_CHANNELS = tuple(range(8, 32))
MOVE_CHANNELS = tuple((32 + 2 * move, 33 + 2 * move) for move in range(12))
_CHANNEL_MOVE = {}
for _move, _channels in enumerate(MOVE_CHANNELS):
    for _channel in _channels:
        _CHANNEL_MOVE[_channel] = _move

_REWARD = StimDesign(160, -1.0, 160, 1.0)


def _color_stim(color):
    level = 0.35 + 0.1 * color
    return StimDesign(160, -level, 160, level)


def _show_colors(neurons, cube):
    for channel, color in zip(SENSE_CHANNELS, cube.facelets):
        neurons.stim(ChannelSet(channel), _color_stim(color))
_FACE_WORDS = {
    "U": "top face",
    "D": "bottom face",
    "L": "left face",
    "R": "right face",
    "F": "front face",
    "B": "back face",
}


def plain_turn(move):
    name = move if isinstance(move, str) else move_name(move)
    if not name:
        return ""
    face = _FACE_WORDS[name[0]]
    if name.endswith("'"):
        return f"{face}, counterclockwise"
    return f"{face}, clockwise"


def _start_controls(commands):
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self._send(204)

        def do_POST(self):
            action = self.path.strip("/")
            if action in ("mix", "solve", "done"):
                commands.put(action)
            self._send(204)

        def _send(self, code):
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _take_commands(commands):
    found = []
    while True:
        try:
            found.append(commands.get_nowait())
        except queue.Empty:
            return found


def play(duration_s, seed=None, commands=None):
    rng = random.Random(seed)
    cube = Cube()
    scramble = []
    last_face = None
    accepted = []
    listen_ticks = int(duration_s * TICKS_PER_SECOND)
    own_server = None
    if commands is None:
        commands = queue.Queue()
        own_server, control_url = _start_controls(commands)
    else:
        control_url = ""
    try:
        return _play(duration_s, rng, cube, scramble, last_face, accepted, listen_ticks, commands, control_url)
    finally:
        if own_server is not None:
            own_server.shutdown()


def _play(duration_s, rng, cube, scramble, last_face, accepted, listen_ticks, commands, control_url):
    controls = "ready"
    with cl.open() as neurons:
        stream = neurons.create_data_stream("cube")
        stamp = -1

        def publish(when, move_code, label, detail, note, needed, loudest):
            nonlocal stamp
            when = int(when)
            if when <= stamp:
                when = stamp + 1
            stamp = when
            stream.append(
                stamp,
                {
                    "facelets": list(cube.facelets),
                    "move": move_code,
                    "label": label,
                    "detail": detail,
                    "note": note,
                    "needed": needed,
                    "loudest": loudest,
                    "solved": label == "The cube is solved",
                    "turns": len(accepted),
                    "control_url": control_url,
                    "controls": controls,
                },
            )

        mixed = None
        remaining = []
        solving = False
        solve_from = None
        hold_until = -1
        last_detail = "The cube is solved."
        announced = False
        pending_mix = []
        next_mix_tick = 0
        solve_requested = False
        awaiting_mixed_banner = False
        mixed_shown = False
        for tick in neurons.loop(
            ticks_per_second=TICKS_PER_SECOND,
            stop_after_seconds=duration_s + 900,
            ignore_jitter=True,
        ):
            when = tick.iteration_next_timestamp
            if not solving:
                if not announced:
                    publish(when, "", "Press Mix", "One click mixes the cube.", "It stops on its own. Then press Solve when you want it to go.", "", "")
                    announced = True
                for action in _take_commands(commands):
                    if action == "mix" and not pending_mix and not awaiting_mixed_banner:
                        mixed_shown = False
                        controls = "scramble"
                        for _ in range(MIX_TURNS):
                            choices = [move for move in range(12) if move // 2 != last_face]
                            move = rng.choice(choices)
                            pending_mix.append(move)
                            last_face = move // 2
                    elif action in ("solve", "done"):
                        solve_requested = True
                if pending_mix and tick.iteration >= next_mix_tick:
                    move = pending_mix.pop(0)
                    cube.apply(move)
                    scramble.append(move)
                    last_detail = plain_turn(move)
                    next_mix_tick = tick.iteration + TICKS_PER_BEAT
                    if not pending_mix:
                        awaiting_mixed_banner = True
                    publish(when, move_name(move), "Mixing", last_detail, "It will stop on its own.", "", "")
                    continue
                if awaiting_mixed_banner and tick.iteration >= next_mix_tick:
                    controls = "ready"
                    awaiting_mixed_banner = False
                    mixed_shown = True
                    publish(when, "", "Mixed", "The mix has stopped.", "Press Solve to show the colors to the dish.", "", "")
                    continue
                if solve_requested and mixed_shown and not pending_mix:
                    solve_requested = False
                    if cube.solved():
                        publish(when, "", "Press Mix", "The cube is still solved.", "Mix it, then press Solve when you want it to go.", "", "")
                    else:
                        mixed = cube.net()
                        solving = True
                        solve_from = tick.iteration
                        controls = "off"
                        choice_counts = [0] * 12
                if not solving:
                    continue
            if solve_from is not None and tick.iteration - solve_from >= listen_ticks:
                tick.loop.stop()
                break
            if cube.solved():
                publish(when, "", "The cube is solved", "Every face is one color.", f"Turns from the dish: {len(accepted)}.", "", "")
                tick.loop.stop()
                break
            beat_index = tick.iteration - solve_from
            if beat_index % TICKS_PER_BEAT == 0:
                _show_colors(neurons, cube)
                choice_counts = [0] * 12
            for spike in tick.analysis.spikes:
                move = _CHANNEL_MOVE.get(spike.channel)
                if move is not None:
                    choice_counts[move] += 1
            if beat_index % TICKS_PER_BEAT != TICKS_PER_BEAT - 1:
                top = max(choice_counts)
                leaders = [move for move, count in enumerate(choice_counts) if count == top and count > 0]
                leader = move_name(leaders[0]) if len(leaders) == 1 else ""
                publish(when, "", "The dish is solving", "The colors are on the dish.", "The dish picks the turn.", leader, "")
                continue
            top = max(choice_counts)
            winners = [move for move, count in enumerate(choice_counts) if count == top and count > 0]
            if len(winners) != 1:
                note = "Several turns are tied, so no turn is taken." if top > 0 else "The dish is quiet, so the cube stays still."
                publish(when, "", "The dish is solving", "The colors are on the dish.", note, "", "")
                continue
            choice = winners[0]
            before = len(cube.solution())
            cube.apply(choice)
            accepted.append(choice)
            last_detail = plain_turn(choice)
            helped = cube.solved() or len(cube.solution()) < before
            if helped:
                neurons.stim(ChannelSet(*MOVE_CHANNELS[choice]), _REWARD)
            if cube.solved():
                publish(when, move_name(choice), "The cube is solved", last_detail, "That turn helped.", "", "")
                tick.loop.stop()
                break
            note = "That turn helped." if helped else "That turn did not help."
            publish(when, move_name(choice), "The dish turned it", last_detail, note, "", "")
        if mixed is None:
            mixed = cube.net()
    solved = cube.solved()
    outcome = "Solved." if solved else "Time ran out before it was solved."
    text = "\n".join(
        [
            outcome,
            "",
            "Your mix:",
            ", ".join(plain_turn(move) for move in scramble),
            "",
            "Mixed cube:",
            mixed,
            "",
            "Turns the dish made:",
            ", ".join(plain_turn(move) for move in accepted) if accepted else "none",
            "",
            "Cube now:",
            cube.net(),
        ]
    )
    return solved, text
