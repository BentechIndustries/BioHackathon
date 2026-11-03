const dataStreams = ["cube", "cl_spikes", "cl_stims"];

const COLORS = ["#f4f6f8", "#d7263d", "#00a86b", "#ffd000", "#ff6a00", "#1f4bff"];
const MOVE_CHANNELS = [
    [8, 9, 10, 11],
    [12, 13, 14, 15],
    [16, 17, 18, 19],
    [20, 21, 22, 23],
    [24, 25, 26, 27],
    [28, 29, 30, 31],
    [32, 33, 34, 35],
    [36, 37, 38, 39],
    [40, 41, 42, 43],
    [44, 45, 46, 47],
    [48, 49, 50, 51],
    [52, 53, 54, 55],
];
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
const CHANNEL_MOVE = new Array(64).fill(-1);
MOVE_CHANNELS.forEach((channels, move) => {
    channels.forEach((channel) => {
        CHANNEL_MOVE[channel] = move;
    });
});

function solvedFacelets() {
    return Array.from({ length: 24 }, (_, index) => Math.floor(index / 4));
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
    const activity = new Array(64).fill(0);
    const pulses = new Array(64).fill(0);
    const queue = [];
    let shown = solvedFacelets();
    let label = "Waiting";
    let lastMove = "";
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

    function reset() {
        activity.fill(0);
        pulses.fill(0);
        queue.length = 0;
        shown = solvedFacelets();
        label = "Waiting";
        lastMove = "";
        turns = 0;
        solved = false;
        anim = null;
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
                }
            }
            return;
        }
        if (dataStreamName !== "cube" || !data || !data.facelets) {
            return;
        }
        queue.push({
            facelets: Array.from(data.facelets),
            move: data.move || "",
            label: data.label || "",
            turns: data.turns || 0,
            solved: Boolean(data.solved),
        });
    }

    function startNext(now) {
        const packet = queue.shift();
        const turn = TURNS[packet.move];
        if (!packet.move || !turn) {
            shown = packet.facelets;
            label = packet.label;
            lastMove = packet.move;
            turns = packet.turns;
            solved = packet.solved;
            return;
        }
        anim = {
            from: shown.slice(),
            to: packet.facelets,
            move: packet.move,
            turn,
            label: packet.label,
            turns: packet.turns,
            solved: packet.solved,
            start: now,
        };
        lastMove = packet.move;
    }

    function draw(browserTimestampMs) {
        for (let index = 0; index < 64; index += 1) {
            activity[index] *= 0.9;
            pulses[index] *= 0.88;
        }
        if (!anim && queue.length) {
            startNext(browserTimestampMs);
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
            label = anim.label;
            if (t >= 1) {
                shown = anim.to;
                label = anim.label;
                turns = anim.turns;
                solved = anim.solved;
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
        const gradient = context.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, "#141a2e");
        gradient.addColorStop(1, "#0b0e18");
        context.fillStyle = gradient;
        context.fillRect(0, 0, width, height);

        const cubeScale = Math.min(width, height) * 0.25;
        const originX = width * 0.27;
        const originY = height * 0.48;
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

        context.fillStyle = "#f4f7fb";
        context.font = `700 ${Math.round(width * 0.034)}px sans-serif`;
        context.fillText(label || "Waiting", width * 0.56, height * 0.1);
        context.fillStyle = solved ? "#7dffb3" : "#9eb0c9";
        context.font = `600 ${Math.round(width * 0.02)}px sans-serif`;
        const moveLine = lastMove ? `Turn ${lastMove}` : "Turn";
        context.fillText(moveLine, width * 0.56, height * 0.16);
        context.fillText(`Turns made ${turns}`, width * 0.56, height * 0.21);
        context.fillStyle = "#7f8da3";
        context.font = `500 ${Math.round(width * 0.016)}px sans-serif`;
        context.fillText("Drag the cube to look around", width * 0.56, height * 0.26);

        const cell = Math.min(width, height) * 0.028;
        const netX = width * 0.56;
        const netY = height * 0.3;
        const gap = cell * 0.18;
        for (const [facelet, col, row] of NET) {
            const x = netX + col * (cell + gap);
            const y = netY + row * (cell + gap);
            roundRect(x, y, cell, cell, cell * 0.18, COLORS[facelets[facelet]]);
        }

        const dishCell = Math.min(width, height) * 0.046;
        const dishX = width * 0.56;
        const dishY = height * 0.56;
        context.fillStyle = "#9eb0c9";
        context.font = `600 ${Math.round(width * 0.018)}px sans-serif`;
        context.textAlign = "left";
        context.textBaseline = "alphabetic";
        context.fillText("Dish", dishX, dishY - dishCell * 0.35);
        const hidden = new Set([0, 4, 7, 56, 63]);
        for (let row = 0; row < 8; row += 1) {
            for (let col = 0; col < 8; col += 1) {
                const channel = col * 8 + row;
                const x = dishX + col * dishCell;
                const y = dishY + row * dishCell;
                const cx = x + dishCell * 0.5;
                const cy = y + dishCell * 0.5;
                const radius = dishCell * 0.32;
                if (hidden.has(channel)) {
                    continue;
                }
                const spike = Math.max(0, Math.min(1, activity[channel] / 4));
                const pulse = Math.max(0, Math.min(1, pulses[channel] / 4));
                context.beginPath();
                context.arc(cx, cy, radius, 0, Math.PI * 2);
                if (pulse > 0.08) {
                    context.fillStyle = `rgba(90, 220, 255, ${0.35 + pulse * 0.65})`;
                } else if (spike > 0.08) {
                    context.fillStyle = `rgba(125, 255, 179, ${0.3 + spike * 0.7})`;
                } else if (CHANNEL_MOVE[channel] >= 0) {
                    context.fillStyle = "#243049";
                } else {
                    context.fillStyle = "#1a2233";
                }
                context.fill();
            }
        }

        context.textAlign = "left";
        context.textBaseline = "alphabetic";
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

    function roundRect(x, y, w, h, radius, color) {
        context.beginPath();
        context.roundRect(x, y, w, h, radius);
        context.fillStyle = color;
        context.fill();
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

export { dataStreams, createVisualiser };
