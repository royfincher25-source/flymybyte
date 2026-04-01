/**
 * Generate SVG icon files from lucide package for font generation.
 * Usage: node generate-icons.js
 */
const fs = require('fs');
const path = require('path');

// Map of Bootstrap icon names → Lucide icon names
const ICON_MAP = {
  'arrow-left': 'arrow-left',
  'info-circle': 'info',
  'gear': 'settings',
  'circle-fill': 'circle',
  'download': 'download',
  'exclamation-triangle': 'triangle-alert',
  'check-circle': 'circle-check',
  'folder': 'folder',
  'file-text': 'file-text',
  'shield-check': 'shield-check',
  'arrow-clockwise': 'refresh-cw',
  'arrow-repeat': 'repeat',
  'hdd': 'hard-drive',
  'key': 'key',
  'list-check': 'list-checks',
  'file-earmark-text': 'file-text',
  'lightning-charge-fill': 'zap',
  'graph-up': 'trending-up',
  'list-ul': 'list',
  'journal-text': 'book-text',
  'activity': 'activity',
  'hdd-network': 'network',
  'globe': 'globe',
  'globe2': 'globe-2',
  'collection': 'collection',
  'search': 'search',
  'memory': 'memory-stick',
  'cpu': 'cpu',
  'database': 'database',
  'wifi': 'wifi',
  'lightning': 'lightning',
  'router': 'router',
  'exclamation-triangle-fill': 'triangle-alert',
  'check-circle-fill': 'circle-check',
  'x-circle-fill': 'circle-x',
  'arrow-up-circle-fill': 'arrow-up-circle',
  'pc-display': 'monitor',
  'cloud-download': 'cloud-download',
  'shield-lock': 'shield-lock',
  'folder2-open': 'folder-open',
  'list': 'menu',
  'x-circle': 'circle-x',
  'lock': 'lock',
  'box-arrow-in-right': 'log-in',
  'box-arrow-right': 'log-out',
  'github': 'github',
  'tag': 'tag',
  'menu-app': 'layout-grid',
  'play': 'play',
  'trash': 'trash-2',
  'x-lg': 'x',
  'terminal': 'terminal',
  'check-lg': 'check',
  'question-circle': 'circle-help',
  'plus-lg': 'plus',
  'dash-lg': 'minus',
  'eye': 'eye',
  'pause': 'pause',
  'play-fill': 'play',
  'stop-fill': 'square',
  'save': 'save',
  'list-task': 'list-todo',
  'bug': 'bug',
  'inbox': 'inbox',
  'arrow-right': 'arrow-right',
};

// Lucide icon definitions (minimal set needed for our 63 icons)
// Each icon is an array: [tag, attrs, children...]
// Based on lucide source: https://github.com/lucide-icons/lucide

const ICONS = {
'arrow-left': [["polyline",{"points":"19 12 5 12 12 19"}],["line",{"x1":"12","y1":"19","x2":"12","y2":"5"}]],
'arrow-right': [["polyline",{"points":"5 12 19 12 12 5"}],["line",{"x1":"12","y1":"5","x2":"12","y2":"19"}]],
'arrow-up-circle': [["circle",{"cx":"12","cy":"12","r":"10"}],["polyline",{"points":"16 12 12 8 8 12"}],["line",{"x1":"12","y1":"16","x2":"12","y2":"8"}]],
'info': [["circle",{"cx":"12","cy":"12","r":"10"}],["path",{"d":"M12 16v-4"}],["path",{"d":"M12 8h.01"}]],
'settings': [["path",{"d":"M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"}],["circle",{"cx":"12","cy":"12","r":"3"}]],
'circle': [["circle",{"cx":"12","cy":"12","r":"10"}]],
'download': [["path",{"d":"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}],["polyline",{"points":"7 10 12 15 17 10"}],["line",{"x1":"12","y1":"15","x2":"12","y2":"3"}]],
'triangle-alert': [["path",{"d":"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"}],["path",{"d":"M12 9v4"}],["path",{"d":"M12 17h.01"}]],
'circle-check': [["circle",{"cx":"12","cy":"12","r":"10"}],["path",{"d":"m9 12 2 2 4-4"}]],
'folder': [["path",{"d":"M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"}]],
'file-text': [["path",{"d":"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"}],["path",{"d":"M14 2v4a2 2 0 0 0 2 2h4"}],["path",{"d":"M10 9H8"}],["path",{"d":"M16 13H8"}],["path",{"d":"M16 17H8"}]],
'shield-check': [["path",{"d":"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["path",{"d":"m9 12 2 2 4-4"}]],
'refresh-cw': [["path",{"d":"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"}],["path",{"d":"M21 3v5h-5"}],["path",{"d":"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"}],["path",{"d":"M8 16H3v5"}]],
'repeat': [["path",{"d":"m17 2 4 4-4 4"}],["path",{"d":"M3 11v-1a4 4 0 0 1 4-4h14"}],["path",{"d":"m7 22-4-4 4-4"}],["path",{"d":"M21 13v1a4 4 0 0 1-4 4H3"}]],
'hard-drive': [["line",{"x1":"22","y1":"12","x2":"2","y2":"12"}],["path",{"d":"M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"}],["path",{"d":"M4 12V7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5"}],["path",{"d":"M12 12v.01"}]],
'key': [["path",{"d":"M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"}],["circle",{"cx":"16.5","cy":"7.5","r":"1.5","fill":"currentColor"}]],
'list-checks': [["path",{"d":"m9 12 2 2 4-4"}],["path",{"d":"m9 6 2 2 4-4"}],["path",{"d":"M16 18h6"}],["path",{"d":"M16 12h6"}]],
'zap': [["polygon",{"points":"13 2 3 14 12 14 11 22 21 10 12 10 13 2"}]],
'trending-up': [["polyline",{"points":"22 7 13.5 15.5 8.5 10.5 2 17"}],["polyline",{"points":"16 7 22 7 22 13"}]],
'list': [["line",{"x1":"8","y1":"6","x2":"21","y2":"6"}],["line",{"x1":"8","y1":"12","x2":"21","y2":"12"}],["line",{"x1":"8","y1":"18","x2":"21","y2":"18"}],["line",{"x1":"3","y1":"6","x2":"3.01","y2":"6"}],["line",{"x1":"3","y1":"12","x2":"3.01","y2":"12"}],["line",{"x1":"3","y1":"18","x2":"3.01","y2":"18"}]],
'book-text': [["path",{"d":"M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"}],["path",{"d":"M8 11h8"}],["path",{"d":"M8 7h6"}]],
'activity': [["path",{"d":"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"}]],
'network': [["rect",{"x":"16","y":"16","width":"6","height":"6","rx":"1"}],["rect",{"x":"2","y":"16","width":"6","height":"6","rx":"1"}],["rect",{"x":"9","y":"2","width":"6","height":"6","rx":"1"}],["path",{"d":"M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"}],["path",{"d":"M12 12V8"}]],
'globe': [["circle",{"cx":"12","cy":"12","r":"10"}],["path",{"d":"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"}],["line",{"x1":"2","y1":"12","x2":"22","y2":"12"}]],
'globe-2': [["path",{"d":"M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z"}],["path",{"d":"M2 12h20"}],["path",{"d":"M12 2a15 15 0 0 1 4 10 15 15 0 0 1-4 10 15 15 0 0 1-4-10 15 15 0 0 1 4-10Z"}],["path",{"d":"M12 2c2.5 3 4 6.5 4 10s-1.5 7-4 10c-2.5-3-4-6.5-4-10s1.5-7 4-10Z"}]],
'collection': [["path",{"d":"M2.5 16.88a1 1 0 0 1-.32-1.43l9-13.02a1 1 0 0 1 1.64 0l9 13.02a1 1 0 0 1-.32 1.43l-8.51 4.69a1 1 0 0 1-.96 0Z"}],["path",{"d":"M6.5 14v6"}],["path",{"d":"M17.5 14v6"}]],
'search': [["circle",{"cx":"11","cy":"11","r":"8"}],["line",{"x1":"21","y1":"21","x2":"16.65","y2":"16.65"}]],
'memory-stick': [["path",{"d":"M6 19v-3"}],["path",{"d":"M10 19v-3"}],["path",{"d":"M14 19v-3"}],["path",{"d":"M18 19v-3"}],["rect",{"width":"16","height":"12","x":"4","y":"3","rx":"2"}],["path",{"d":"M8 8h.01"}],["path",{"d":"M12 8h.01"}],["path",{"d":"M16 8h.01"}],["path",{"d":"M8 12h.01"}],["path",{"d":"M12 12h.01"}],["path",{"d":"M16 12h.01"}]],
'cpu': [["rect",{"width":"16","height":"16","x":"4","y":"4","rx":"2"}],["rect",{"width":"6","height":"6","x":"9","y":"9","rx":"1"}],["path",{"d":"M15 2v2"}],["path",{"d":"M15 20v2"}],["path",{"d":"M2 15h2"}],["path",{"d":"M2 9h2"}],["path",{"d":"M20 15h2"}],["path",{"d":"M20 9h2"}],["path",{"d":"M9 2v2"}],["path",{"d":"M9 20v2"}]],
'database': [["ellipse",{"cx":"12","cy":"5","rx":"9","ry":"3"}],["path",{"d":"M3 5V19A9 3 0 0 0 21 19V5"}],["path",{"d":"M3 12A9 3 0 0 0 21 12"}]],
'wifi': [["path",{"d":"M12 20h.01"}],["path",{"d":"M8.5 16.429a5 5 0 0 1 7 0"}],["path",{"d":"M5.636 13.564a9 9 0 0 1 12.728 0"}],["path",{"d":"M2.764 10.706C5.08 8.39 8.41 7 12 7s6.92 1.39 9.236 3.706"}]],
'lightning': [["polygon",{"points":"13 2 3 14 12 14 11 22 21 10 12 10 13 2"}]],
'router': [["rect",{"width":"20","height":"8","x":"2","y":"14","rx":"2"}],["path",{"d":"M6.01 18H6"}],["path",{"d":"M10.01 18H10"}],["path",{"d":"M15 10v2"}],["path",{"d":"M15 2v2"}],["path",{"d":"M15 16v2"}],["path",{"d":"M9.5 6.5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5"}],["path",{"d":"M12 2a7 7 0 0 1 7 7"}],["path",{"d":"M5 9a7 7 0 0 1 7-7"}]],
'circle-x': [["circle",{"cx":"12","cy":"12","r":"10"}],["path",{"d":"m15 9-6 6"}],["path",{"d":"m9 9 6 6"}]],
'monitor': [["rect",{"width":"20","height":"14","x":"2","y":"3","rx":"2"}],["line",{"x1":"8","y1":"21","x2":"16","y2":"21"}],["line",{"x1":"12","y1":"17","x2":"12","y2":"21"}]],
'cloud-download': [["path",{"d":"M12 13v8l-4-4"}],["path",{"d":"M12 13v8l4-4"}],["path",{"d":"M20 16.58A5 5 0 0 0 18 7h-1.26A8 8 0 1 0 4 15.25"}]],
'shield-lock': [["path",{"d":"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["rect",{"width":"4","height":"4","x":"10","y":"12"}],["path",{"d":"M12 16v2"}],["path",{"d":"M10 16h4"}]],
'folder-open': [["path",{"d":"m6 14 1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.94 1.5H5a2 2 0 0 1-2-2V7.38"}],["path",{"d":"M20 10V8a2 2 0 0 0-2-2h-5.5"}],["path",{"d":"M20 10H4a2 2 0 0 0-2 2v7"}],["path",{"d":"M2 10h18"}]],
'menu': [["line",{"x1":"4","y1":"12","x2":"20","y2":"12"}],["line",{"x1":"4","y1":"6","x2":"20","y2":"6"}],["line",{"x1":"4","y1":"18","x2":"20","y2":"18"}]],
'lock': [["rect",{"width":"18","height":"11","x":"3","y":"11","rx":"2","ry":"2"}],["path",{"d":"M7 11V7a5 5 0 0 1 10 0v4"}]],
'log-in': [["path",{"d":"M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"}],["polyline",{"points":"12 8 16 12 12 16"}],["line",{"x1":"16","y1":"12","x2":"3","y2":"12"}]],
'log-out': [["path",{"d":"M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"}],["polyline",{"points":"16 17 21 12 16 7"}],["line",{"x1":"21","y1":"12","x2":"9","y2":"12"}]],
'github': [["path",{"d":"M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.61-.22 1.25-.15 1.88v4"}],["path",{"d":"M9 18c-4.51 2-5-2-7-2"}]],
'tag': [["path",{"d":"M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"}],["circle",{"cx":"7.5","cy":"7.5","r":".5","fill":"currentColor"}]],
'layout-grid': [["rect",{"width":"7","height":"7","x":"3","y":"3","rx":"1"}],["rect",{"width":"7","height":"7","x":"14","y":"3","rx":"1"}],["rect",{"width":"7","height":"7","x":"14","y":"14","rx":"1"}],["rect",{"width":"7","height":"7","x":"3","y":"14","rx":"1"}]],
'play': [["polygon",{"points":"6 3 20 12 6 21 6 3"}]],
'trash-2': [["path",{"d":"M3 6h18"}],["path",{"d":"M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"}],["path",{"d":"M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"}],["line",{"x1":"10","y1":"11","x2":"10","y2":"17"}],["line",{"x1":"14","y1":"11","x2":"14","y2":"17"}]],
'x': [["path",{"d":"M18 6 6 18"}],["path",{"d":"m6 6 12 12"}]],
'terminal': [["polyline",{"points":"4 17 10 11 4 5"}],["line",{"x1":"12","y1":"19","x2":"20","y2":"19"}]],
'check': [["path",{"d":"M20 6 9 17l-5-5"}]],
'circle-help': [["circle",{"cx":"12","cy":"12","r":"10"}],["path",{"d":"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"}],["path",{"d":"M12 17h.01"}]],
'plus': [["path",{"d":"M5 12h14"}],["path",{"d":"M12 5v14"}]],
'minus': [["path",{"d":"M5 12h14"}]],
'eye': [["path",{"d":"M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"}],["circle",{"cx":"12","cy":"12","r":"3"}]],
'pause': [["rect",{"width":"4","height":"16","x":"6","y":"4"}],["rect",{"width":"4","height":"16","x":"14","y":"4"}]],
'square': [["rect",{"width":"18","height":"18","x":"3","y":"3","rx":"2"}]],
'save': [["path",{"d":"M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"}],["path",{"d":"M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"}],["path",{"d":"M7 3v4a1 1 0 0 0 1 1h7"}]],
'list-todo': [["rect",{"x":"3","y":"5","width":"6","height":"6","rx":"1"}],["path",{"d":"m3 17 2 2 4-4"}],["path",{"d":"M13 6h8"}],["path",{"d":"M13 12h8"}],["path",{"d":"M13 18h8"}]],
'bug': [["path",{"d":"m8 2 1.88 1.88"}],["path",{"d":"M14.12 3.88 16 2"}],["path",{"d":"M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"}],["path",{"d":"M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"}],["path",{"d":"M12 20v-9"}],["path",{"d":"M6.53 9C4.6 8.8 3 7.1 3 5"}],["path",{"d":"M6 13H2"}],["path",{"d":"M3 21c0-2.1 1.7-3.9 3.8-4"}],["path",{"d":"M20.97 5c0 2.1-1.6 3.8-3.5 4"}],["path",{"d":"M22 13h-4"}],["path",{"d":"M17.2 17c2.1.1 3.8 1.9 3.8 4"}]],
'inbox': [["path",{"d":"M20.86 8.776a2 2 0 0 0-1.79-1.234H17V5a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v2.542H4.93a2 2 0 0 0-1.79 1.234L2 14v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-7.224Z"}],["path",{"d":"M16 15H8v-3a4 4 0 0 1 8 0v3Z"}]],
};

const SVG_HEADER = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">`;
const SVG_FOOTER = `</svg>`;

function attrsToString(attrs) {
  return Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(' ');
}

function elementToString(el) {
  const [tag, attrs, ...children] = el;
  const attrStr = attrs ? ` ${attrsToString(attrs)}` : '';
  if (children.length === 0) {
    return `<${tag}${attrStr}/>`;
  }
  const childStr = children.map(c => typeof c === 'string' ? c : elementToString(c)).join('');
  return `<${tag}${attrStr}>${childStr}</${tag}>`;
}

function generateSVG(iconName) {
  const elements = ICONS[iconName];
  if (!elements) return null;
  const content = elements.map(el => elementToString(el)).join('\n  ');
  return `${SVG_HEADER}\n  ${content}\n${SVG_FOOTER}`;
}

const outputDir = path.join(__dirname, 'svg');
fs.mkdirSync(outputDir, { recursive: true });

let generated = 0;
for (const [name] of Object.entries(ICON_MAP)) {
  const lucideName = ICON_MAP[name];
  const svg = generateSVG(lucideName);
  if (svg) {
    fs.writeFileSync(path.join(outputDir, `${name}.svg`), svg);
    generated++;
  } else {
    console.warn(`Warning: Could not generate SVG for ${name} (lucide: ${lucideName})`);
  }
}

console.log(`Generated ${generated} SVG files in ${outputDir}`);
