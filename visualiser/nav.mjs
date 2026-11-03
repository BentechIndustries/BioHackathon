// Live view of a navigation session for the CL data-stream visualiser (see session.ipynb).
// Left: the room from above with the agent, its eight rays and the current episode's trail.
// Right: the 8x8 electrode array; sensory electrodes flash when pulsed, motor regions glow
// with their firing rate relative to the session maximum.
function createVisualiser(uniqueId, div)
{
    const CELL = 5, PAD = 16, MEA = 22;
    const canvas = div.querySelector('canvas');
    const ctx    = canvas.getContext('2d');
    const status = div.querySelector('#status');

    let attrs, mapImage, latest, trail, flash, maxRate;

    function reset()
    {
        attrs = null; mapImage = null; latest = null; trail = []; flash = new Map(); maxRate = 1;
    }

    function buildMap()
    {
        const rows = attrs.map.length, cols = attrs.map[0].length;
        mapImage = document.createElement('canvas');
        mapImage.width = cols * CELL; mapImage.height = rows * CELL;
        const m = mapImage.getContext('2d');
        const colours = { '#': '#222', '.': '#eee', ' ': '#999' };
        for (let r = 0; r < rows; r++)
            for (let c = 0; c < cols; c++)
            {
                m.fillStyle = colours[attrs.map[r][c]];
                m.fillRect(c * CELL, (rows - 1 - r) * CELL, CELL, CELL);   // z grows upwards
            }
        canvas.width  = mapImage.width + 2 * PAD + 8 * MEA;
        canvas.height = Math.max(mapImage.height, 8 * MEA + 40);
    }

    function attributesReset(name, initial)
    {
        if (name !== 'nav') return;
        attrs = initial;
        buildMap();
    }

    function attributesUpdated(name, updated)
    {
        if (name !== 'nav' || !attrs) return;
        attrs = { ...attrs, ...updated };
    }

    function process(name, timestamp, data)
    {
        if (name !== 'nav') return;
        if (latest && data.ep !== latest.ep) trail = [];
        if (data.state === 'play') trail.push([data.x, data.z]);
        for (const ch of data.stim) flash.set(ch, 1.0);
        maxRate = Math.max(maxRate, ...data.rate);
        latest = data;
    }

    function toPixel(x, z)
    {
        const rows = attrs.map.length;
        return [(x - attrs.origin[0]) / attrs.res * CELL, (rows - (z - attrs.origin[1]) / attrs.res) * CELL];
    }

    function drawRoom()
    {
        ctx.drawImage(mapImage, 0, 0);
        const [gx, gz] = toPixel(...attrs.goal);
        ctx.fillStyle = 'gold';
        ctx.beginPath(); ctx.arc(gx, gz, attrs.goal_radius / attrs.res * CELL, 0, 2 * Math.PI); ctx.fill();
        if (!latest) return;

        ctx.strokeStyle = '#4a7'; ctx.lineWidth = 2; ctx.beginPath();
        trail.forEach(([x, z], i) => { const [px, pz] = toPixel(x, z); i ? ctx.lineTo(px, pz) : ctx.moveTo(px, pz); });
        ctx.stroke();

        const [ax, az] = toPixel(latest.x, latest.z);
        latest.rays.forEach((d, k) =>
        {
            const a = latest.h + attrs.ray_angles[k];
            const [ex, ez] = toPixel(latest.x + d * Math.cos(a), latest.z + d * Math.sin(a));
            ctx.strokeStyle = `rgba(230, 60, 60, ${0.25 + 0.75 * (1 - d / attrs.ray_max)})`;
            ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(ax, az); ctx.lineTo(ex, ez); ctx.stroke();
        });
        ctx.fillStyle = latest.state === 'pause' ? '#e33' : '#27f';
        ctx.beginPath(); ctx.arc(ax, az, 0.2 / attrs.res * CELL, 0, 2 * Math.PI); ctx.fill();
        const [hx, hz] = toPixel(latest.x + 0.3 * Math.cos(latest.h), latest.z + 0.3 * Math.sin(latest.h));
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(ax, az); ctx.lineTo(hx, hz); ctx.stroke();
    }

    function drawArray()
    {
        const x0 = mapImage.width + PAD, sensory = new Set(attrs.sensory);
        const motor = [new Set(attrs.motor[0]), new Set(attrs.motor[1])];
        ctx.fillStyle = '#111'; ctx.fillRect(x0, 0, 8 * MEA, canvas.height);
        for (let ch = 0; ch < 64; ch++)
        {
            const row = ch % 8, col = Math.floor(ch / 8);
            let colour = '#333';
            if (sensory.has(ch)) colour = `rgb(${80 + 175 * (flash.get(ch) || 0)}, 60, 60)`;
            for (const side of [0, 1])
                if (motor[side].has(ch))
                {
                    const level = latest ? Math.min(latest.rate[side] / maxRate, 1) : 0;
                    colour = `rgb(40, ${70 + 185 * level}, ${side ? 200 : 90})`;
                }
            ctx.fillStyle = colour;
            ctx.fillRect(x0 + col * MEA + 2, row * MEA + 2, MEA - 4, MEA - 4);
        }
        ctx.fillStyle = '#ccc'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('turn left', x0 + MEA, 8 * MEA + 14);
        ctx.fillText('rays', x0 + 4 * MEA, 8 * MEA + 14);
        ctx.fillText('turn right', x0 + 7 * MEA, 8 * MEA + 14);
        ctx.textAlign = 'start';
        for (const [ch, v] of flash) flash.set(ch, v * 0.85);
    }

    function draw()
    {
        if (!attrs) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawRoom();
        drawArray();
        if (latest)
            status.textContent =
                `${attrs.condition}  episode ${attrs.episode}  ${latest.state.padEnd(9)} t=${latest.t.toFixed(1)}s` +
                `   goals ${attrs.counts.goal}  collisions ${attrs.counts.collision}  timeouts ${attrs.counts.timeout}` +
                `   turn ${latest.turn >= 0 ? '+' : ''}${latest.turn.toFixed(2)} rad/s`;
    }

    return { bufferMs: 1000 / 60, reset, attributesReset, attributesUpdated, process, draw };
}
