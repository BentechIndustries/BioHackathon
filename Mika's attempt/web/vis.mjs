const dataStreams = ["cube", "cl_spikes", "cl_stims"];

const COLORS = ["#f4f6f8", "#d7263d", "#00a86b", "#ffd000", "#ff6a00", "#1f4bff"];
const SENSE_START = 8;
const MOVE_CHANNELS = Array.from({ length: 12 }, (_, move) => [32 + move * 2, 33 + move * 2]);
const TURNS = {
    "U": { axis: "y", angle: -90, side: 1 },
    "U'": { axis: "y", angle: 90, side: 1 },
    "D": { axis: "y", angle: 90, side: -1 },
    "D'": { axis: "y", angle: -90, side: -1 },
    "R": { axis: "x", angle: -90, side: 1 },
    "R'": { axis: "x", angle: 90, side: 1 },
    "L": { axis: "x", angle: 90, side: -1 },
    "L'": { axis: "x", angle: -90, side: -1 },
    "F": { axis: "z", angle: -90, side: 1 },
    "F'": { axis: "z", angle: 90, side: 1 },
    "B": { axis: "z", angle: 90, side: -1 },
    "B'": { axis: "z", angle: -90, side: -1 },
};
const NET = [
    [0, 2, 0], [1, 3, 0], [2, 2, 1], [3, 3, 1],
    [16, 0, 2], [17, 1, 2], [18, 0, 3], [19, 1, 3],
    [8, 2, 2], [9, 3, 2], [10, 2, 3], [11, 3, 3],
    [4, 4, 2], [5, 5, 2], [6, 4, 3], [7, 5, 3],
    [20, 6, 2], [21, 7, 2], [22, 6, 3], [23, 7, 3],
    [12, 2, 4], [13, 3, 4], [14, 2, 5], [15, 3, 5],
];

const NORMALS = {
    U: [0, 1, 0],
    D: [0, -1, 0],
    R: [1, 0, 0],
    L: [-1, 0, 0],
    F: [0, 0, 1],
    B: [0, 0, -1],
};
const TANGENTS = {
    U: [[1, 0, 0], [0, 0, 1]],
    D: [[1, 0, 0], [0, 0, -1]],
    R: [[0, 0, -1], [0, 1, 0]],
    L: [[0, 0, 1], [0, 1, 0]],
    F: [[1, 0, 0], [0, 1, 0]],
    B: [[-1, 0, 0], [0, 1, 0]],
};
const CUBIES = [
    { at: [-0.5, 0.5, -0.5], faces: [["U", 0], ["B", 21], ["L", 16]] },
    { at: [0.5, 0.5, -0.5], faces: [["U", 1], ["R", 5], ["B", 20]] },
    { at: [-0.5, 0.5, 0.5], faces: [["U", 2], ["L", 17], ["F", 8]] },
    { at: [0.5, 0.5, 0.5], faces: [["U", 3], ["F", 9], ["R", 4]] },
    { at: [-0.5, -0.5, 0.5], faces: [["D", 12], ["F", 10], ["L", 19]] },
    { at: [0.5, -0.5, 0.5], faces: [["D", 13], ["R", 6], ["F", 11]] },
    { at: [-0.5, -0.5, -0.5], faces: [["D", 14], ["L", 18], ["B", 23]] },
    { at: [0.5, -0.5, -0.5], faces: [["D", 15], ["B", 22], ["R", 7]] },
];

function buildStickers() {
    const stickers = new Array(24);
    const half = 0.38;
    const lift = 0.02;
    for (const cubie of CUBIES) {
        for (const [face, index] of cubie.faces) {
            const n = NORMALS[face];
            const [t, s] = TANGENTS[face];
            const ox = cubie.at[0] + n[0] * (0.5 + lift);
            const oy = cubie.at[1] + n[1] * (0.5 + lift);
            const oz = cubie.at[2] + n[2] * (0.5 + lift);
            const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => [
                ox + t[0] * half * a + s[0] * half * b,
                oy + t[1] * half * a + s[1] * half * b,
                oz + t[2] * half * a + s[2] * half * b,
            ]);
            const plastic = 0.52;
            const px = cubie.at[0] + n[0] * 0.5;
            const py = cubie.at[1] + n[1] * 0.5;
            const pz = cubie.at[2] + n[2] * 0.5;
            const body = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) => [
                px + t[0] * plastic * a + s[0] * plastic * b,
                py + t[1] * plastic * a + s[1] * plastic * b,
                pz + t[2] * plastic * a + s[2] * plastic * b,
            ]);
            stickers[index] = {
                corners,
                body,
                center: [ox, oy, oz],
                face,
            };
        }
    }
    return stickers;
}

const STICKERS = buildStickers();
const MOVE_CODES = ["U", "U'", "R", "R'", "F", "F'", "D", "D'", "L", "L'", "B", "B'"];
const PLAIN_TURNS = {
    "U": "top face, clockwise",
    "U'": "top face, counterclockwise",
    "D": "bottom face, clockwise",
    "D'": "bottom face, counterclockwise",
    "R": "right face, clockwise",
    "R'": "right face, counterclockwise",
    "L": "left face, clockwise",
    "L'": "left face, counterclockwise",
    "F": "front face, clockwise",
    "F'": "front face, counterclockwise",
    "B": "back face, clockwise",
    "B'": "back face, counterclockwise",
};
const PERMS = [[2,0,3,1,20,21,6,7,4,5,10,11,12,13,14,15,8,9,18,19,16,17,22,23],[1,3,0,2,8,9,6,7,16,17,10,11,12,13,14,15,20,21,18,19,4,5,22,23],[0,9,2,11,6,4,7,5,8,13,10,15,12,22,14,20,16,17,18,19,3,21,1,23],[0,22,2,20,5,7,4,6,8,1,10,3,12,9,14,11,16,17,18,19,15,21,13,23],[0,1,19,17,2,5,3,7,10,8,11,9,6,4,14,15,16,12,18,13,20,21,22,23],[0,1,4,6,13,5,12,7,9,11,8,10,17,19,14,15,16,3,18,2,20,21,22,23],[0,1,2,3,4,5,10,11,8,9,18,19,14,12,15,13,16,17,22,23,20,21,6,7],[0,1,2,3,4,5,22,23,8,9,6,7,13,15,12,14,16,17,10,11,20,21,18,19],[23,1,21,3,4,5,6,7,0,9,2,11,8,13,10,15,18,16,19,17,20,14,22,12],[8,1,10,3,4,5,6,7,12,9,14,11,23,13,21,15,17,19,16,18,20,2,22,0],[5,7,2,3,4,15,6,14,8,9,10,11,12,13,16,18,1,17,0,19,22,20,23,21],[18,16,2,3,4,0,6,1,8,9,10,11,12,13,7,5,14,17,15,19,21,23,20,22]];
const CHANNEL_MOVE = new Array(64).fill(-1);
MOVE_CHANNELS.forEach((channels, move) => {
    channels.forEach((channel) => {
        CHANNEL_MOVE[channel] = move;
    });
});

function solvedFacelets() {
    return Array.from({ length: 24 }, (_, index) => Math.floor(index / 4));
}

function applyMove(state, move) {
    const perm = PERMS[move];
    const next = new Array(24);
    for (let index = 0; index < 24; index += 1) {
        next[index] = state[perm[index]];
    }
    return next;
}

function solveFacelets(start) {
    const solved = solvedFacelets();
    const key = (state) => state.join(",");
    const startKey = key(start);
    const solvedKey = key(solved);
    if (startKey === solvedKey) {
        return [];
    }
    const forwardParent = new Map([[startKey, [null, null]]]);
    const backwardParent = new Map([[solvedKey, [null, null]]]);
    let forwardQueue = [start.slice()];
    let backwardQueue = [solved.slice()];
    let meeting = null;

    function expand(queue, parent, other) {
        const next = [];
        for (const state of queue) {
            const stateKey = key(state);
            for (let move = 0; move < 12; move += 1) {
                const child = applyMove(state, move);
                const childKey = key(child);
                if (parent.has(childKey)) {
                    continue;
                }
                parent.set(childKey, [stateKey, move]);
                if (other.has(childKey)) {
                    return { meeting: childKey, next };
                }
                next.push(child);
            }
        }
        return { meeting: null, next };
    }

    while (forwardQueue.length && backwardQueue.length && meeting === null) {
        if (forwardParent.size <= backwardParent.size) {
            const result = expand(forwardQueue, forwardParent, backwardParent);
            meeting = result.meeting;
            forwardQueue = result.next;
        } else {
            const result = expand(backwardQueue, backwardParent, forwardParent);
            meeting = result.meeting;
            backwardQueue = result.next;
        }
    }
    if (meeting === null) {
        return [];
    }
    const prefix = [];
    let node = meeting;
    while (forwardParent.get(node)[0] !== null) {
        const [previous, move] = forwardParent.get(node);
        prefix.push(move);
        node = previous;
    }
    prefix.reverse();
    const suffix = [];
    node = meeting;
    while (backwardParent.get(node)[0] !== null) {
        const [previous, move] = backwardParent.get(node);
        suffix.push(move ^ 1);
        node = previous;
    }
    return prefix.concat(suffix);
}

function rotatePoint(point, axis, angle) {
    const [x, y, z] = point;
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    if (axis === "y") {
        return [x * c + z * s, y, -x * s + z * c];
    }
    if (axis === "x") {
        return [x, y * c - z * s, y * s + z * c];
    }
    return [x * c - y * s, x * s + y * c, z];
}

function project(point, yaw, pitch) {
    const [x, y, z] = point;
    const x1 = x * Math.cos(yaw) + z * Math.sin(yaw);
    const z1 = -x * Math.sin(yaw) + z * Math.cos(yaw);
    const y2 = y * Math.cos(pitch) - z1 * Math.sin(pitch);
    const z2 = y * Math.sin(pitch) + z1 * Math.cos(pitch);
    return { x: x1, y: -y2, depth: z2 };
}

function axisIndex(axis) {
    if (axis === "x") return 0;
    if (axis === "y") return 1;
    return 2;
}

function createVisualiser(uniqueId, div) {
    const canvas = div.querySelector(".cube-canvas");
    const context = canvas.getContext("2d");
    const dishCanvas = div.querySelector(".dish-canvas");
    const dishContext = dishCanvas ? dishCanvas.getContext("2d") : null;
    const netCanvas = div.querySelector(".net-canvas");
    const netContext = netCanvas ? netCanvas.getContext("2d") : null;
    const titleEl = div.querySelector(".cube-title");
    const detailEl = div.querySelector(".cube-detail");
    const noteEl = div.querySelector(".cube-note");
    const activity = new Array(64).fill(0);
    const pulses = new Array(64).fill(0);
    const queue = [];
    let shown = solvedFacelets();
    let label = "Waiting";
    let detail = "";
    let note = "";
    let needed = "";
    let loudest = "";
    let turns = 0;
    let solved = false;
    let anim = null;
    let dpr = 1;
    let yaw = -0.62;
    let pitch = 0.46;
    let dragging = false;
    let lastPointerX = 0;
    let lastPointerY = 0;

    canvas.style.touchAction = "none";
    canvas.addEventListener("pointerdown", (event) => {
        dragging = true;
        lastPointerX = event.clientX;
        lastPointerY = event.clientY;
        canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
        if (!dragging) {
            return;
        }
        const dx = event.clientX - lastPointerX;
        const dy = event.clientY - lastPointerY;
        lastPointerX = event.clientX;
        lastPointerY = event.clientY;
        yaw += dx * 0.01;
        pitch = Math.max(-1.15, Math.min(1.15, pitch + dy * 0.01));
    });
    canvas.addEventListener("pointerup", () => {
        dragging = false;
    });
    canvas.addEventListener("pointercancel", () => {
        dragging = false;
    });

    const mixButton = div.querySelector(".mix-button");
    const solveButton = div.querySelector(".solve-button");
    let controlUrl = "";
    let faceletState = solvedFacelets();
    let lastFace = null;
    let mixing = false;
    let solveQueued = false;
    let dishOn = false;
    let vote = new Array(12).fill(0);
    let nextVoteAt = 0;

    function showStatus(labelText, detailText, noteText, mode) {
        readStatus({
            label: labelText,
            detail: detailText,
            note: noteText,
            needed: "",
            loudest: "",
            turns: 0,
            solved: false,
            controls: mode || "ready",
        });
    }

    function localMix() {
        if (mixing || solveQueued) {
            return;
        }
        mixing = true;
        showStatus("Mixing", "The cube is being scrambled.", "It will stop on its own.", "scramble");
        for (let turn = 0; turn < 6; turn += 1) {
            const choices = [];
            for (let move = 0; move < 12; move += 1) {
                if ((move >> 1) !== lastFace) {
                    choices.push(move);
                }
            }
            const move = choices[Math.floor(Math.random() * choices.length)];
            lastFace = move >> 1;
            faceletState = applyMove(faceletState, move);
            const code = MOVE_CODES[move];
            queue.push({
                facelets: faceletState.slice(),
                move: code,
                label: "Mixing",
                detail: PLAIN_TURNS[code],
                note: "It will stop on its own.",
                needed: "",
                loudest: "",
                turns: 0,
                solved: false,
                controls: "scramble",
            });
        }
    }

    function localSolve() {
        if (mixing || solveQueued) {
            return;
        }
        if (!solveFacelets(faceletState).length) {
            showStatus("Press Mix", "The cube is still solved.", "Mix it, then press Solve to show the colors to the dish.");
            return;
        }
        solveQueued = true;
        dishOn = true;
        vote = new Array(12).fill(0);
        nextVoteAt = performance.now() + 900;
        showStatus("The dish is solving", "The colors are on the dish.", "The dish picks each turn.", "off");
        lastFace = null;
    }

    function sendControl(action) {
        if (!controlUrl) {
            if (action === "mix") {
                localMix();
            } else if (action === "solve") {
                localSolve();
            }
            return;
        }
        fetch(`${controlUrl}/${action}`, { method: "POST" }).catch(() => {});
    }

    if (mixButton) {
        mixButton.addEventListener("click", () => sendControl("mix"));
    }
    if (solveButton) {
        solveButton.addEventListener("click", () => sendControl("solve"));
    }

    function reset() {
        activity.fill(0);
        pulses.fill(0);
        queue.length = 0;
        shown = solvedFacelets();
        label = "Waiting";
        detail = "";
        note = "";
        needed = "";
        loudest = "";
        turns = 0;
        solved = false;
        anim = null;
        syncCopy();
        draw(performance.now(), 0);
    }

    function process(dataStreamName, timestamp, data) {
        if (dataStreamName === "cl_spikes" || dataStreamName === "cl_stims") {
            const channel = data && data.channel;
            if (channel >= 0 && channel < 64) {
                if (dataStreamName === "cl_stims") {
                    pulses[channel] = Math.min(6, pulses[channel] + 1.4);
                } else {
                    activity[channel] = Math.min(6, activity[channel] + 1);
                    const move = CHANNEL_MOVE[channel];
                    if (dishOn && move >= 0) {
                        vote[move] += 1;
                    }
                }
            }
            return;
        }
        if (dataStreamName !== "cube" || !data || !data.facelets) {
            return;
        }
        const packet = {
            facelets: Array.from(data.facelets),
            move: data.move || "",
            label: data.label || "",
            detail: data.detail || "",
            note: data.note || "",
            needed: data.needed || "",
            loudest: data.loudest || "",
            turns: data.turns || 0,
            solved: Boolean(data.solved),
            control_url: data.control_url || "",
            controls: data.controls || "",
        };
        faceletState = packet.facelets.slice();
        readStatus(packet);
        if (!packet.move) {
            return;
        }
        queue.push(packet);
    }

    function readStatus(packet) {
        label = packet.label || label;
        detail = packet.detail || "";
        note = packet.note || "";
        needed = packet.needed || "";
        loudest = packet.loudest || "";
        turns = packet.turns || 0;
        solved = Boolean(packet.solved);
        if (packet.solved) {
            solveQueued = false;
            needed = "";
            loudest = "";
        }
        if (packet.control_url) {
            controlUrl = packet.control_url;
        }
        const mode = packet.controls || "";
        const locked = mode === "off" || mode === "scramble";
        if (mixButton) {
            mixButton.disabled = locked;
        }
        if (solveButton) {
            solveButton.disabled = locked;
        }
        syncCopy();
    }

    function syncCopy() {
        if (titleEl) {
            titleEl.textContent = label || "Waiting";
            titleEl.classList.toggle("is-solved", solved);
        }
        if (detailEl) {
            detailEl.textContent = detail || "";
        }
        if (noteEl) {
            noteEl.textContent = note || "";
        }
    }

    function startNext(now) {
        const packet = queue.shift();
        const turn = TURNS[packet.move];
        if (!packet.move || !turn) {
            shown = packet.facelets;
            readStatus(packet);
            return;
        }
        anim = {
            from: shown.slice(),
            to: packet.facelets,
            move: packet.move,
            turn,
            start: now,
        };
        readStatus(packet);
    }

    function draw(browserTimestampMs) {
        for (let index = 0; index < 64; index += 1) {
            activity[index] *= 0.9;
            pulses[index] *= 0.88;
        }
        if (!anim && queue.length) {
            startNext(browserTimestampMs);
        } else if (mixing && !anim && !queue.length) {
            mixing = false;
            showStatus("Mixed", "The mix has stopped.", "Press Solve to show the colors to the dish.");
        } else if (dishOn && !anim && !queue.length && browserTimestampMs >= nextVoteAt) {
            nextVoteAt = browserTimestampMs + 900;
            const top = Math.max(...vote);
            const winners = [];
            vote.forEach((count, move) => {
                if (count === top && count > 0) {
                    winners.push(move);
                }
            });
            vote = new Array(12).fill(0);
            if (winners.length !== 1) {
                showStatus(
                    "The dish is solving",
                    "The colors are on the dish.",
                    winners.length ? "Several turns are tied, so no turn is taken." : "The dish is quiet, so the cube stays still.",
                    "off",
                );
            } else {
                const move = winners[0];
                const before = solveFacelets(faceletState).length;
                faceletState = applyMove(faceletState, move);
                const after = solveFacelets(faceletState).length;
                const helped = after < before;
                const code = MOVE_CODES[move];
                if (helped) {
                    for (const channel of MOVE_CHANNELS[move]) {
                        pulses[channel] = 4;
                    }
                }
                if (after === 0) {
                    dishOn = false;
                }
                needed = code;
                queue.push({
                    facelets: faceletState.slice(),
                    move: code,
                    label: after === 0 ? "The cube is solved" : "The dish turned it",
                    detail: PLAIN_TURNS[code],
                    note: helped ? "That turn helped." : "That turn did not help.",
                    needed: "",
                    loudest: "",
                    turns: 0,
                    solved: after === 0,
                    controls: after === 0 ? "ready" : "off",
                });
            }
        }
        let facelets = shown;
        let angle = 0;
        let turn = null;
        if (anim) {
            const t = Math.min(1, (browserTimestampMs - anim.start) / 460);
            const eased = 1 - Math.pow(1 - t, 3);
            angle = anim.turn.angle * eased * Math.PI / 180;
            turn = anim.turn;
            facelets = anim.from;
            if (t >= 1) {
                shown = anim.to;
                anim = null;
                facelets = shown;
                angle = 0;
                turn = null;
            }
        }
        paint(facelets, turn, angle);
    }

    function paint(facelets, turn, angle) {
        dpr = window.devicePixelRatio || 1;
        const wrap = canvas.parentElement;
        const width = Math.max(1, wrap.clientWidth);
        const height = Math.max(1, wrap.clientHeight);
        const pixelWidth = Math.round(width * dpr);
        const pixelHeight = Math.round(height * dpr);
        if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
            canvas.width = pixelWidth;
            canvas.height = pixelHeight;
        }
        context.setTransform(dpr, 0, 0, dpr, 0, 0);
        context.clearRect(0, 0, width, height);

        const cubeScale = Math.min(width, height) * 0.3;
        const originX = width * 0.5;
        const originY = height * 0.48;
        context.fillStyle = "rgba(0, 0, 0, 0.28)";
        context.beginPath();
        context.ellipse(originX, originY + cubeScale * 1.05, cubeScale * 0.95, cubeScale * 0.18, 0, 0, Math.PI * 2);
        context.fill();
        const drawn = [];
        for (let index = 0; index < 24; index += 1) {
            const sticker = STICKERS[index];
            const moving = turn && sticker.center[axisIndex(turn.axis)] * turn.side > 0.2;
            const mapPoint = (point) => (moving ? rotatePoint(point, turn.axis, angle) : point);
            const body = sticker.body.map(mapPoint).map((point) => project(point, yaw, pitch));
            const corners = sticker.corners.map(mapPoint).map((point) => project(point, yaw, pitch));
            const depth = corners.reduce((sum, point) => sum + point.depth, 0) / corners.length;
            drawn.push({ body, corners, depth, color: facelets[index] });
        }
        drawn.sort((a, b) => a.depth - b.depth);
        for (const face of drawn) {
            fillPoly(face.body, originX, originY, cubeScale, "#141414");
            fillPoly(face.corners, originX, originY, cubeScale, COLORS[face.color]);
        }
        paintNet(facelets);
        paintDish(facelets);
    }

    function fitCanvas(target, targetContext) {
        if (!target || !targetContext) {
            return null;
        }
        const width = Math.max(1, target.clientWidth);
        const height = Math.max(1, target.clientHeight);
        const pixelWidth = Math.round(width * dpr);
        const pixelHeight = Math.round(height * dpr);
        if (target.width !== pixelWidth || target.height !== pixelHeight) {
            target.width = pixelWidth;
            target.height = pixelHeight;
        }
        targetContext.setTransform(dpr, 0, 0, dpr, 0, 0);
        targetContext.clearRect(0, 0, width, height);
        return { width, height };
    }

    function paintNet(facelets) {
        const size = fitCanvas(netCanvas, netContext);
        if (!size) {
            return;
        }
        const cell = Math.min(size.height / 6.4, size.width / 8.6);
        const gap = cell * 0.16;
        const gridWidth = 8 * cell + 7 * gap;
        const gridHeight = 6 * cell + 5 * gap;
        const netX = (size.width - gridWidth) / 2;
        const netY = (size.height - gridHeight) / 2;
        for (const [facelet, col, row] of NET) {
            roundRect(
                netContext,
                netX + col * (cell + gap),
                netY + row * (cell + gap),
                cell,
                cell,
                cell * 0.22,
                COLORS[facelets[facelet]],
            );
        }
    }

    function paintDish(facelets) {
        const size = fitCanvas(dishCanvas, dishContext);
        if (!size) {
            return;
        }
        const hidden = new Set([0, 4, 7, 56, 63]);
        const pad = 8;
        const cell = Math.min((size.width - pad * 2) / 8, (size.height - pad * 2) / 8);
        const grid = cell * 8;
        const originX = (size.width - grid) / 2;
        const originY = (size.height - grid) / 2;
        const spot = (channel) => {
            const col = Math.floor(channel / 8);
            const row = channel % 8;
            return {
                x: originX + col * cell,
                y: originY + row * cell,
            };
        };
        for (let move = 0; move < MOVE_CHANNELS.length; move += 1) {
            const code = MOVE_CODES[move];
            let color = "";
            if (code === needed) {
                color = "#f4f7fb";
            } else if (code === loudest) {
                color = "#ffb020";
            }
            if (!color) {
                continue;
            }
            let minX = Infinity;
            let minY = Infinity;
            let maxX = -Infinity;
            let maxY = -Infinity;
            for (const channel of MOVE_CHANNELS[move]) {
                const at = spot(channel);
                minX = Math.min(minX, at.x);
                minY = Math.min(minY, at.y);
                maxX = Math.max(maxX, at.x + cell);
                maxY = Math.max(maxY, at.y + cell);
            }
            const inset = cell * 0.08;
            dishContext.beginPath();
            dishContext.roundRect(minX + inset, minY + inset, maxX - minX - inset * 2, maxY - minY - inset * 2, cell * 0.28);
            dishContext.strokeStyle = color;
            dishContext.lineWidth = Math.max(2, cell * 0.08);
            dishContext.stroke();
        }
        for (let channel = 0; channel < 64; channel += 1) {
            if (hidden.has(channel)) {
                continue;
            }
            const at = spot(channel);
            const cx = at.x + cell * 0.5;
            const cy = at.y + cell * 0.5;
            const radius = cell * 0.26;
            const spike = Math.max(0, Math.min(1, activity[channel] / 4));
            const pulse = Math.max(0, Math.min(1, pulses[channel] / 4));
            const sense = channel - SENSE_START;
            dishContext.beginPath();
            dishContext.arc(cx, cy, radius, 0, Math.PI * 2);
            if (sense >= 0 && sense < 24 && facelets) {
                dishContext.fillStyle = COLORS[facelets[sense]];
            } else if (CHANNEL_MOVE[channel] >= 0) {
                dishContext.fillStyle = "#2a354c";
            } else {
                dishContext.fillStyle = "#1a2233";
            }
            dishContext.fill();
            if (pulse > 0.08) {
                dishContext.beginPath();
                dishContext.arc(cx, cy, radius + 3, 0, Math.PI * 2);
                dishContext.strokeStyle = `rgba(90, 220, 255, ${0.45 + pulse * 0.55})`;
                dishContext.lineWidth = 2;
                dishContext.stroke();
            } else if (spike > 0.08) {
                dishContext.beginPath();
                dishContext.arc(cx, cy, radius + 2, 0, Math.PI * 2);
                dishContext.strokeStyle = `rgba(125, 255, 179, ${0.4 + spike * 0.6})`;
                dishContext.lineWidth = 2;
                dishContext.stroke();
            }
        }
    }

    function fillPoly(points, originX, originY, scale, color) {
        context.beginPath();
        points.forEach((point, index) => {
            const x = originX + point.x * scale;
            const y = originY + point.y * scale;
            if (index === 0) context.moveTo(x, y);
            else context.lineTo(x, y);
        });
        context.closePath();
        context.fillStyle = color;
        context.fill();
    }

    function roundRect(target, x, y, w, h, radius, color) {
        target.beginPath();
        target.roundRect(x, y, w, h, radius);
        target.fillStyle = color;
        target.fill();
    }

    reset();

    return {
        bufferMs: 40,
        reset,
        process,
        draw,
        attributesReset() {},
        attributesUpdated() {},
    };
}

export { dataStreams, createVisualiser, solveFacelets, applyMove };
