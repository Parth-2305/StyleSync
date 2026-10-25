// Full-screen sparkle effect for the Outfit Matcher. One <canvas>, ~100 small stars, removed when finished.
// Kept light on purpose (no shadows/blur, DPR capped at 2) so it never makes the page feel laggy.

const SPARKLE_COLORS = ["#FF6B6B", "#FFD166", "#A0C8E8", "#FFFFFF", "#FF9AA2"];

// A 4-point star: 8 points that alternate between the outer and inner radius.
function drawStar(ctx, x, y, radius, rotation) {
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const r = i % 2 === 0 ? radius : radius * 0.28;
    const angle = rotation + (i * Math.PI) / 4;
    ctx.lineTo(x + Math.cos(angle) * r, y + Math.sin(angle) * r);
  }
  ctx.closePath();
  ctx.fill();
}

// `origin` = {x, y} in screen pixels: the burst flies out from there (e.g. the Match button).
function sparkleBurst(origin) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const canvas = document.createElement("canvas");
  canvas.className = "sparkle-canvas";
  canvas.width = window.innerWidth * ratio;
  canvas.height = window.innerHeight * ratio;
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);

  const rand = (min, max) => min + Math.random() * (max - min);
  const color = () => SPARKLE_COLORS[Math.floor(Math.random() * SPARKLE_COLORS.length)];
  const startTime = performance.now();
  let lastTime = startTime;

  // 35 stars fly out of the button, 70 twinkle in at random spots across the whole screen.
  const stars = [
    ...Array.from({ length: 35 }, () => ({
      x: origin.x, y: origin.y, vx: rand(-9, 9), vy: rand(-11, 3), delay: 0, life: rand(700, 1100), size: rand(5, 11), color: color(),
    })),
    ...Array.from({ length: 70 }, () => ({
      x: rand(0, window.innerWidth), y: rand(0, window.innerHeight), vx: 0, vy: 0, delay: rand(0, 600), life: rand(600, 1000), size: rand(6, 14), color: color(),
    })),
  ];

  function frame(now) {
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    const elapsed = now - startTime;
    const step = Math.min((now - lastTime) / 16.67, 3); // 1 = one 60 Hz frame, so 60 Hz and 144 Hz screens look the same
    lastTime = now;
    let alive = 0;
    for (const s of stars) {
      const t = (elapsed - s.delay) / s.life; // 0 → 1 over the star's life
      if (t >= 1) continue;
      alive++;
      if (t < 0) continue;
      s.x += s.vx * step; s.y += s.vy * step; // fly out, slow down, drift down
      s.vx *= 0.96 ** step;
      s.vy = s.vy * 0.96 ** step + 0.25 * step;
      ctx.globalAlpha = Math.sin(Math.PI * t); // fade in, then out
      ctx.fillStyle = s.color;
      drawStar(ctx, s.x, s.y, s.size * (0.5 + Math.sin(Math.PI * t)), t * 3);
    }
    if (alive) requestAnimationFrame(frame);
    else canvas.remove();
  }
  requestAnimationFrame(frame);
}
