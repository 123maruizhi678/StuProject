/* 高级感动效层：电影感粒子背景 + 视频背景槽 + 鼠标跟随光晕 + KPI 数字滚动
   遵循"克制动效"原则：背景负责氛围、内容负责信息；尊重 prefers-reduced-motion。 */
(function () {
  "use strict";
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- 1) 电影感柔光粒子（蓝/青/紫缓慢上浮，模拟微动视频） ---------- */
  const canvas = document.getElementById("bgCanvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const COLORS = ["91,140,255", "34,211,238", "167,139,250", "255,255,255"];
    let w = 0, h = 0, t = 0, particles = [];

    function resize() {
      w = window.innerWidth; h = window.innerHeight;
      canvas.style.width = w + "px"; canvas.style.height = h + "px";
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function make(anywhere) {
      return {
        x: Math.random() * w,
        y: anywhere ? Math.random() * h : h + 12,
        r: 0.4 + Math.random() * 1.8,
        base: 0.10 + Math.random() * 0.40,
        vy: 0.12 + Math.random() * 0.45,
        vx: (Math.random() - 0.5) * 0.18,
        wob: Math.random() * Math.PI * 2,
        wobS: 0.004 + Math.random() * 0.006,
        ph: Math.random() * Math.PI * 2,
        tw: 0.002 + Math.random() * 0.004,
        c: COLORS[(Math.random() * COLORS.length) | 0],
      };
    }
    function spawn() {
      const n = Math.min(110, Math.floor((w * h) / 16000));
      particles = Array.from({ length: n }, () => make(true));
    }
    function tick() {
      ctx.clearRect(0, 0, w, h);
      t++;
      for (const p of particles) {
        p.y -= p.vy;
        p.x += p.vx + Math.sin(p.wob + t * p.wobS) * 0.16;
        p.ph += p.tw;
        const a = p.base * (0.5 + 0.5 * Math.sin(p.ph));
        if (p.y < -12) Object.assign(p, make(false));
        if (p.x < -12) p.x = w + 12; else if (p.x > w + 12) p.x = -12;
        const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 5);
        glow.addColorStop(0, "rgba(" + p.c + "," + a.toFixed(3) + ")");
        glow.addColorStop(1, "rgba(" + p.c + ",0)");
        ctx.fillStyle = glow;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = "rgba(" + p.c + "," + Math.min(1, a * 1.7).toFixed(3) + ")";
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
      }
      requestAnimationFrame(tick);
    }
    resize(); spawn();
    window.addEventListener("resize", () => { resize(); spawn(); });
    if (!reduce) requestAnimationFrame(tick);
  }

  /* ---------- 2) 视频背景槽（放入 frontend/assets/bg.mp4 或 bg.webm 即自动启用） ---------- */
  const video = document.getElementById("bgVideo");
  if (video) {
    (async () => {
      for (const src of ["/static/assets/bg.mp4", "/static/assets/bg.webm"]) {
        try {
          const r = await fetch(src, { method: "HEAD" });
          if (r.ok) { video.src = src; video.classList.add("ready"); break; }
        } catch (e) { /* 未找到则继续使用粒子背景 */ }
      }
    })();
  }

  /* ---------- 3) 鼠标跟随光晕（径向柔光，缓慢跟手） ---------- */
  const spot = document.createElement("div");
  spot.className = "spotlight";
  spot.setAttribute("aria-hidden", "true");
  document.body.appendChild(spot);
  if (!reduce) {
    let tx = -620, ty = -620, cx = -620, cy = -620, shown = false;
    document.addEventListener("pointermove", (e) => {
      tx = e.clientX; ty = e.clientY;
      if (!shown) { shown = true; spot.style.opacity = "1"; }
    }, { passive: true });
    document.addEventListener("mouseleave", () => { shown = false; spot.style.opacity = "0"; });
    (function loop() {
      cx += (tx - cx) * 0.10;
      cy += (ty - cy) * 0.10;
      spot.style.transform = "translate(" + (cx - 310) + "px," + (cy - 310) + "px)";
      requestAnimationFrame(loop);
    })();
  }

  /* ---------- 4) KPI 数字从 0 滚动到目标值 ---------- */
  function countUp(el) {
    if (reduce || el.dataset.counted) return;
    el.dataset.counted = "1";
    const raw = (el.textContent || "0").replace(/[^\d.\-]/g, "");
    const target = parseFloat(raw) || 0;
    if (target === 0) return;
    const dec = (raw.split(".")[1] || "").length;
    const dur = 700, start = performance.now();
    el.textContent = "0";
    function tick(now) {
      const p = Math.min(1, (now - start) / dur);
      const v = target * (1 - Math.pow(1 - p, 3));
      el.textContent = v.toLocaleString("zh-CN", { maximumFractionDigits: dec, minimumFractionDigits: dec });
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  function scan(root) { root.querySelectorAll(".kpi .value").forEach(countUp); }
  const app = document.getElementById("app");
  if (app) {
    scan(app);
    new MutationObserver(() => scan(app)).observe(app, { childList: true, subtree: true });
  }
})();
