import React from 'react';

const shapes = {
  shield: <><path d="m12 22 0 0C7 20 4 16.6 4 12V5l8-3 8 3v7c0 4.6-3 8-8 10Z"/><path d="m9 12 2 2 4-4"/></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
  monitor: <><rect x="2" y="4" width="20" height="14" rx="2"/><path d="M8 22h8M12 18v4"/></>,
  activity: <path d="M2 12h4l3-7 5 14 3-7h5"/>,
  users: <><path d="M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 20v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
  clipboard: <><rect x="4" y="4" width="16" height="18" rx="2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="m8 14 2 2 5-5"/></>,
  chart: <><path d="M3 3v18h18"/><path d="m7 15 5-5 4 3 5-7"/></>,
  settings: <><path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.07.07-2.86 2.86-.07-.07A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1.2 1.6v.1h-4v-.1A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.07.07-2.86-2.86.07-.07A1.7 1.7 0 0 0 4.2 15 1.7 1.7 0 0 0 2.6 13.8h-.1v-4h.1A1.7 1.7 0 0 0 4.2 8.6a1.7 1.7 0 0 0-.34-1.88l-.07-.07 2.86-2.86.07.07A1.7 1.7 0 0 0 8.6 4.2 1.7 1.7 0 0 0 9.8 2.6v-.1h4v.1A1.7 1.7 0 0 0 15 4.2a1.7 1.7 0 0 0 1.88-.34l.07-.07 2.86 2.86-.07.07A1.7 1.7 0 0 0 19.4 8.6a1.7 1.7 0 0 0 1.6 1.2h.1v4H21a1.7 1.7 0 0 0-1.6 1.2Z"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  chevron: <path d="m9 18 6-6-6-6"/>,
  refresh: <><path d="M20 11a8 8 0 0 0-14-5L3 9"/><path d="M3 4v5h5M4 13a8 8 0 0 0 14 5l3-3"/><path d="M16 15h5v5"/></>,
  download: <><path d="M12 3v12m-4-4 4 4 4-4"/><path d="M4 17v4h16v-4"/></>,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></>,
  lock: <><rect x="4" y="10" width="16" height="12" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3"/></>,
  check: <path d="m4 12 5 5L20 6"/>,
  alert: <><path d="M10.3 3.5 1.8 18.1A2 2 0 0 0 3.6 21h16.8a2 2 0 0 0 1.8-2.9L13.7 3.5a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 4h.01"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  database: <><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></>,
  filter: <><path d="M3 5h18M6 12h12M10 19h4"/></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
  close: <path d="M5 5l14 14M19 5 5 19"/>,
  external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/></>,
  file: <><path d="M6 2h8l5 5v15H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z"/><path d="M14 2v6h5M8 13h8m-8 4h8"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></>,
  key: <><circle cx="8" cy="15" r="5"/><path d="m12 11 9-9M17 6l3 3"/></>,
  server: <><rect x="3" y="3" width="18" height="8" rx="2"/><rect x="3" y="13" width="18" height="8" rx="2"/><path d="M7 7h.01M7 17h.01M11 7h6m-6 10h6"/></>,
};

export default function Icon({ name = 'info', size = 20, className = '', strokeWidth = 1.8 }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name] ?? shapes.info}</svg>;
}
