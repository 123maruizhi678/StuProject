// 同一套描边图标，不依赖外部字体或 CDN。
const paths = {
  overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  assistant:'M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z',
  todos:'M9 5h10v16H5V5h4 M9 3h6v4H9z M8 12h8 M8 16h5',
  customer:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M17 4a4 4 0 0 1 0 7 M22 21v-2a4 4 0 0 0-3-3.87',
  students:'M2 9l10-5 10 5-10 5z M6 11v6c4 3 8 3 12 0v-6 M22 9v7',
  courses:'M4 4h7a4 4 0 0 1 1 1 4 4 0 0 1 1-1h7v16h-7a4 4 0 0 0-1 1 4 4 0 0 0-1-1H4z M12 5v16',
  scores:'M4 20V10h4v10 M10 20V4h4v16 M16 20v-8h4v8',
  tickets:'M4 4h16v13H9l-5 4z M8 8h8 M8 12h5',
  notifications:'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4',
  employees:'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M5 21v-2a7 7 0 0 1 14 0v2',
  departments:'M9 3h6v5H9z M3 16h6v5H3z M15 16h6v5h-6z M12 8v4 M6 16v-4h12v4',
  knowledge:'M5 3h12l3 3v15H5z M14 3v5h6 M8 12h9 M8 16h6',
  audit:'M12 2l8 3v6c0 6-8 11-8 11S4 17 4 11V5z M9 11l2 2 4-4',
  menu:'M4 6h16 M4 12h16 M4 18h16',
  arrow:'M5 12h14 M13 6l6 6-6 6',
  logout:'M9 4H4v16h5 M10 12h11 M17 8l4 4-4 4'
};
export function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('fill','none');
  svg.setAttribute('stroke','currentColor'); svg.setAttribute('stroke-width','1.6');
  svg.setAttribute('stroke-linecap','round'); svg.setAttribute('stroke-linejoin','round');
  svg.setAttribute('aria-hidden','true');
  const path=document.createElementNS('http://www.w3.org/2000/svg','path');
  path.setAttribute('d',paths[name] || paths.courses); svg.append(path); return svg;
}
