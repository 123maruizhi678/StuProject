/* 轻量 SVG 图表库 —— 遵循 dataviz 规范：细标记、2px 间隙、4px 圆角数据端、
   2px 折线、十字准线 + 悬浮提示、文字使用文本色而非系列色。 */
export const Viz = (() => {
  const NS = "http://www.w3.org/2000/svg";

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function ink() {
    return {
      text: cssVar("--text"), muted: cssVar("--muted"),
      grid: cssVar("--grid"), surface: cssVar("--surface"),
      baseline: cssVar("--border-strong"),
    };
  }
  function fmt(n) {
    if (n == null) return "";
    return Number(n).toLocaleString("zh-CN");
  }
  function el(name, attrs = {}) {
    const e = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    return e;
  }
  function makeTooltip(host) {
    const tip = document.createElement("div");
    tip.className = "viz-tooltip";
    host.appendChild(tip);
    return tip;
  }
  function showTip(tip, x, y, html) {
    tip.innerHTML = html;
    tip.style.display = "block";
    const host = tip.parentElement;
    const r = host.getBoundingClientRect();
    let left = x + 14, top = y + 14;
    if (left + tip.offsetWidth > r.width) left = x - tip.offsetWidth - 12;
    if (top + tip.offsetHeight > r.height) top = y - tip.offsetHeight - 10;
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  /* ---------- 折线 / 面积图（单系列） ---------- */
  function lineArea(host, opts) {
    const { labels, values, color = "#2a78d6", height = 210, title } = opts;
    const W = 620, H = height;
    const PAD = { l: 42, r: 16, t: 18, b: 30 };
    const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
    const c = ink();

    host.innerHTML = "";
    host.classList.add("chart-wrap");
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title || "趋势图" });
    const tip = makeTooltip(host);
    host.appendChild(svg);

    const max = Math.max(1, ...values) * 1.15;
    const x = (i) => PAD.l + (values.length === 1 ? iw / 2 : (i / (values.length - 1)) * iw);
    const y = (v) => PAD.t + ih - (v / max) * ih;

    // 网格线（1px，实线，弱化）
    const ticks = 4;
    for (let t = 0; t <= ticks; t++) {
      const v = (max / ticks) * t;
      const yy = y(v);
      svg.appendChild(el("line", { x1: PAD.l, y1: yy, x2: W - PAD.r, y2: yy,
        stroke: c.grid, "stroke-width": 1 }));
      const lab = el("text", { x: PAD.l - 8, y: yy + 4, "text-anchor": "end",
        "font-size": 11, fill: c.muted, "font-family": "inherit" });
      lab.textContent = fmt(Math.round(v));
      svg.appendChild(lab);
    }

    // 面积填充（10% 透明）
    let areaD = `M ${x(0)} ${y(values[0])}`;
    values.forEach((v, i) => { areaD += ` L ${x(i)} ${y(v)}`; });
    areaD += ` L ${x(values.length - 1)} ${PAD.t + ih} L ${x(0)} ${PAD.t + ih} Z`;
    svg.appendChild(el("path", { d: areaD, fill: color, opacity: 0.10 }));

    // 折线（2px，圆角）
    let lineD = values.map((v, i) => `${i ? "L" : "M"} ${x(i)} ${y(v)}`).join(" ");
    svg.appendChild(el("path", { d: lineD, fill: "none", stroke: color,
      "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));

    // 末端圆点（8px + 2px 表面环）
    const lastI = values.length - 1;
    svg.appendChild(el("circle", { cx: x(lastI), cy: y(values[lastI]), r: 6,
      fill: c.surface, stroke: c.surface, "stroke-width": 2 }));
    svg.appendChild(el("circle", { cx: x(lastI), cy: y(values[lastI]), r: 4, fill: color }));

    // X 轴标签
    labels.forEach((lb, i) => {
      if (labels.length > 8 && i % Math.ceil(labels.length / 8) !== 0 && i !== labels.length - 1) return;
      const t = el("text", { x: x(i), y: H - 8, "text-anchor": "middle", "font-size": 11, fill: c.muted, "font-family": "inherit" });
      t.textContent = lb;
      svg.appendChild(t);
    });

    // 十字准线 + 悬浮提示
    const cross = el("line", { y1: PAD.t, y2: PAD.t + ih, stroke: c.muted,
      "stroke-width": 1, opacity: 0.0, "stroke-dasharray": "3 3" });
    svg.appendChild(cross);
    svg.addEventListener("mousemove", (e) => {
      const r = svg.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * W;
      let idx = Math.round(((px - PAD.l) / iw) * (values.length - 1));
      idx = Math.max(0, Math.min(values.length - 1, idx));
      cross.setAttribute("x1", x(idx)); cross.setAttribute("x2", x(idx));
      cross.setAttribute("opacity", 1);
      showTip(tip, ((x(idx) / W) * r.width), ((y(values[idx]) / H) * r.height),
        `<div class="tt-val">${fmt(values[idx])}</div><div class="muted">${labels[idx]}</div>`);
    });
    svg.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); tip.style.display = "none"; });
  }

  /* ---------- 水平条形图（分布） ---------- */
  function hBars(host, opts) {
    const { items, height = 30, title, colorField = "color" } = opts;
    const c = ink();
    const W = 620, barH = Math.min(24, height), gap = 2;
    const H = items.length * (barH + gap) + 8;
    const labelW = 120, PAD_R = 44, topPad = 4;
    const iw = W - labelW - PAD_R;

    host.innerHTML = "";
    host.classList.add("chart-wrap");
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title || "分布图" });
    const tip = makeTooltip(host);
    host.appendChild(svg);

    const max = Math.max(1, ...items.map(i => i.value));
    items.forEach((it, idx) => {
      const color = it[colorField] || cssVar("--s1");
      const yy = topPad + idx * (barH + gap);
      const w = Math.max(4, (it.value / max) * iw);

      // 标签（文本色）
      const lab = el("text", { x: labelW - 10, y: yy + barH / 2 + 4, "text-anchor": "end",
        "font-size": 12, fill: c.text, "font-family": "inherit" });
      lab.textContent = it.label;
      svg.appendChild(lab);

      // 条（细标记，数据端圆角，基线直角，2px 间隙）
      svg.appendChild(el("rect", { x: labelW, y: yy, width: w, height: barH, rx: 4, fill: color }));

      // 数值（条端）
      const val = el("text", { x: labelW + w + 8, y: yy + barH / 2 + 4, "font-size": 12,
        fill: c.text, "font-family": "inherit" });
      val.textContent = fmt(it.value);
      svg.appendChild(val);

      // 悬浮命中区（大于标记）
      const hit = el("rect", { x: labelW, y: yy - 2, width: Math.max(w, iw), height: barH + 4,
        fill: "transparent" });
      hit.addEventListener("mousemove", (e) => {
        const r = svg.getBoundingClientRect();
        showTip(tip, e.clientX - r.left, e.clientY - r.top,
          `<div>${it.label}</div><div class="tt-val">${fmt(it.value)}</div>`);
      });
      hit.addEventListener("mouseleave", () => { tip.style.display = "none"; });
      svg.appendChild(hit);
    });
  }

  return { lineArea, hBars, fmt, cssVar };
})();
