import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Icon from './Icon.jsx';

const NAV = [
  { id: 'overview', text: 'Overview', icon: 'grid' },
  { id: 'devices', text: 'Devices', icon: 'monitor' },
  { id: 'events', text: 'Access events', icon: 'activity' },
  { id: 'accounts', text: 'Accounts & roles', icon: 'users' },
  { id: 'reviews', text: 'Access reviews', icon: 'clipboard' },
  { id: 'reports', text: 'Reports', icon: 'chart' },
];

const number = (value) => new Intl.NumberFormat('en-US').format(Number(value) || 0);
const dateValue = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};
const fullDate = (value) => {
  const date = dateValue(value);
  return date ? date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Not reported';
};
const relativeDate = (value) => {
  const date = dateValue(value);
  if (!date) return 'No events yet';
  const diff = Math.max(0, Date.now() - date.getTime());
  if (diff < 60_000) return 'Less than a minute ago';
  if (diff < 60 * 60_000) return `${Math.floor(diff / 60_000)} min ago`;
  if (diff < 24 * 60 * 60_000) return `${Math.floor(diff / 3600000)} hr ago`;
  return date.toLocaleDateString();
};

function saveTextFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function csvCell(value) {
  const raw = String(value ?? '');
  // Prevent formulas from executing in spreadsheet programs.
  const safe = /^[\s]*[=+@\-]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replaceAll('"', '""')}"`;
}
function makeCsv(devices) {
  return [
    ['Device ID', 'Event count', 'Last event UTC'].map(csvCell).join(','),
    ...devices.map((device) => [device.device_id, device.event_count, device.last_event_utc ?? ''].map(csvCell).join(',')),
  ].join('\r\n');
}

function Brand({ compact = false }) {
  return <div className="brand">
    <div className="brand-logo"><Icon name="shield" size={23} strokeWidth={2.1} /></div>
    {!compact && <div className="brand-name">Access<span>Review</span><small>SECURITY CONSOLE</small></div>}
  </div>;
}
function MiniStatus({ ok, children }) {
  return <span className={`status-pill ${ok ? 'success' : 'neutral'}`}><span className="status-dot" />{children}</span>;
}
function EmptyGraphic({ icon = 'database' }) {
  return <div className="empty-art"><div className="empty-art-inner"><Icon name={icon} size={29} /></div></div>;
}
function IconButton({ icon, title, onClick, disabled = false }) {
  return <button type="button" className="icon-button" onClick={onClick} aria-label={title} title={title} disabled={disabled}><Icon name={icon} size={18} /></button>;
}
function Panel({ title, subtitle, action, children, className = '' }) {
  return <section className={`panel ${className}`}>
    {(title || subtitle || action) && <header className="panel-heading"><div>{title && <h2>{title}</h2>}{subtitle && <p>{subtitle}</p>}</div>{action}</header>}
    {children}
  </section>;
}
function StatCard({ icon, label, value, note, style = '' }) {
  return <article className="stat-card">
    <div className="stat-card-top"><span className={`stat-icon ${style}`}><Icon name={icon} size={20} /></span><span className="stat-decoration" /></div>
    <div className="stat-value">{value}</div><div className="stat-name">{label}</div><div className="stat-note">{note}</div>
  </article>;
}
function NoData({ heading, description, icon = 'monitor' }) {
  return <div className="empty-state"><EmptyGraphic icon={icon} /><h3>{heading}</h3><p>{description}</p></div>;
}

function Login({ onConnect, loading, error }) {
  const [enteredToken, setEnteredToken] = useState('');
  const [reveal, setReveal] = useState(false);
  return <div className="login-shell">
    <section className="login-visual">
      <div className="login-visual-content">
        <Brand />
        <div className="visual-copy"><span className="eyebrow light">CENTRALIZED ACCESS GOVERNANCE</span><h1>Complete visibility.<br /><em>Confident decisions.</em></h1><p>A single place to review security telemetry from Windows and Linux devices.</p></div>
        <div className="visual-flow"><div><Icon name="monitor" /><span>Windows & Linux</span></div><span className="flow-line"/><div><Icon name="server"/><span>FastAPI</span></div><span className="flow-line"/><div><Icon name="database"/><span>PostgreSQL</span></div></div>
        <p className="visual-footer">AccessReviewAgent · Prototype security dashboard</p>
      </div>
      <div className="orb orb-one"/><div className="orb orb-two"/><div className="grid-decoration"/>
    </section>
    <section className="login-form-pane">
      <div className="login-mobile-brand"><Brand /></div>
      <div className="login-card">
        <div className="small-label"><span className="small-purple-dot"/> ADMIN ACCESS</div>
        <h2>Welcome back</h2><p className="login-intro">Connect securely to your AccessReview workspace.</p>
        <form onSubmit={(event) => {event.preventDefault(); onConnect(enteredToken);}}>
          <label className="field-label" htmlFor="admin-token">Admin API token</label>
          <div className="input-token"><Icon name="lock" size={18}/><input id="admin-token" type={reveal ? 'text' : 'password'} value={enteredToken} onChange={(event)=>setEnteredToken(event.target.value)} autoComplete="off" placeholder="Enter ADMIN_API_TOKEN" minLength={1} required/><button type="button" className="reveal-button" onClick={()=>setReveal((v)=>!v)}>{reveal ? 'Hide' : 'Show'}</button></div>
          <div className="endpoint-label"><Icon name="server" size={15} /> Connects via secure same-origin API proxy</div>
          {error && <div className="form-error" role="alert"><Icon name="alert" size={17}/><span>{error}</span></div>}
          <button className="primary-button connect-button" type="submit" disabled={loading || !enteredToken.trim()}>{loading ? <><Icon name="refresh" size={17} className="spin"/> Connecting…</> : <>Connect to dashboard <Icon name="arrow" size={18}/></>}</button>
        </form>
        <div className="login-security"><Icon name="shield" size={17}/><span>Token stays in this browser tab's memory. It is not saved to local storage.</span></div>
      </div>
      <div className="login-credit">Built for the AccessReviewAgent prototype</div>
    </section>
  </div>;
}

function DeviceTable({ devices, filter = '', showSearch = false }) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('events');
  const visible = useMemo(() => {
    const matched = devices.filter((device) => device.device_id.toLowerCase().includes((filter || query).toLowerCase()));
    return matched.sort((a, b) => {
      if (sort === 'name') return a.device_id.localeCompare(b.device_id);
      if (sort === 'latest') return (dateValue(b.last_event_utc)?.getTime() || 0) - (dateValue(a.last_event_utc)?.getTime() || 0);
      return b.event_count - a.event_count;
    });
  }, [devices, filter, query, sort]);
  return <>
    {showSearch && <div className="table-toolbar"><div className="search-box"><Icon name="search" size={18}/><input type="search" value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Search device ID…" aria-label="Search device ID"/></div><div className="sort-control"><Icon name="filter" size={16}/><select value={sort} onChange={(e)=>setSort(e.target.value)} aria-label="Sort devices"><option value="events">Most events</option><option value="latest">Latest activity</option><option value="name">Device ID</option></select></div></div>}
    {!visible.length ? <NoData icon="monitor" heading={devices.length ? 'No matching devices' : 'No devices reporting events'} description={devices.length ? 'Try a different device ID.' : 'Once your agents send events, devices will appear here automatically.'}/> :
    <div className="table-scroll"><table className="data-table"><thead><tr><th>DEVICE</th><th>RECORDED EVENTS</th><th>LAST EVENT</th><th>EVENT DATA</th></tr></thead><tbody>{visible.map((device)=><tr key={device.device_id}>
      <td><div className="device-name"><span className="device-avatar"><Icon name="monitor" size={18}/></span><span><strong>{device.device_id}</strong><small>Agent device ID</small></span></div></td>
      <td><span className="table-count">{number(device.event_count)}</span></td>
      <td><span className="table-time">{relativeDate(device.last_event_utc)}<small>{fullDate(device.last_event_utc)}</small></span></td>
      <td><MiniStatus ok={Number(device.event_count)>0}>Recorded</MiniStatus></td>
    </tr>)}</tbody></table></div>}
  </>;
}

function Distribution({ devices }) {
  const top = [...devices].sort((a,b)=>b.event_count-a.event_count).slice(0,5);
  const max = Math.max(...top.map((device)=>device.event_count), 1);
  return <Panel title="Event distribution" subtitle="Recorded events by device">
    {!top.length ? <NoData heading="No event data yet" description="Device event totals will appear after the first successful agent uploads." icon="chart" /> : <div className="distribution-list">
      {top.map((device, i)=><div className="distribution-item" key={device.device_id}><div className="distribution-top"><span className="bar-name">{device.device_id}</span><strong>{number(device.event_count)}</strong></div><div className="bar-track"><div className={`bar-fill tone-${i%5}`} style={{width:`${Math.max(2, device.event_count / max * 100)}%`}}/></div></div>)}
    </div>}
    <div className="panel-footnote"><Icon name="info" size={15}/> Counts are cumulative, not a time-series trend.</div>
  </Panel>;
}

function Overview({ summary, devices, goTo }) {
  const total = devices.reduce((sum, device) => sum + device.event_count, 0);
  const timestamps = devices.map((device) => dateValue(device.last_event_utc)?.getTime()).filter(Boolean);
  const latest = timestamps.length ? new Date(Math.max(...timestamps)).toISOString() : null;
  return <>
    <div className="intro-bar"><div><div className="eyebrow">SECURITY OVERVIEW</div><h1>Workspace overview</h1><p>Real-time refresh of the data your agents have uploaded.</p></div><span className="updated-chip"><span className="pulse-dot"/> Ingest API connected</span></div>
    <div className="stat-grid">
      <StatCard icon="monitor" label="Devices with events" value={number(devices.length)} note="Based on event records" style="purple"/>
      <StatCard icon="activity" label="Events ingested" value={number(total)} note="Across all devices" style="blue"/>
      <StatCard icon="database" label="Account snapshots" value={number(summary.snapshots)} note="Total snapshots received" style="orange"/>
      <StatCard icon="clock" label="Latest recorded event" value={latest ? relativeDate(latest) : '—'} note={latest ? fullDate(latest) : 'No events available'} style="green"/>
    </div>
    <div className="overview-grid"><Distribution devices={devices}/>
      <Panel title="System health" subtitle="Ingestion and data availability"><div className="health-stack">
        <div className="health-item"><span className="health-icon good"><Icon name="check" size={19}/></span><div><strong>Admin API reachable</strong><p>Authenticated summary request succeeded</p></div><MiniStatus ok>Ready</MiniStatus></div>
        <div className="health-item"><span className="health-icon neutral"><Icon name="database" size={18}/></span><div><strong>Snapshot records</strong><p>{number(summary.snapshots)} stored account snapshots</p></div></div>
        <div className="health-item"><span className="health-icon neutral"><Icon name="info" size={19}/></span><div><strong>Detailed log browsing</strong><p>Needs additional read-only API endpoints</p></div></div>
      </div><div className="health-note"><Icon name="info" size={16}/> Devices with no events may not appear. Recent events do not prove an agent is online.</div></Panel>
    </div>
    <Panel title="Devices reporting events" subtitle="Latest results from your current PostgreSQL records" action={<button className="text-button" onClick={()=>goTo('devices')}>View all devices <Icon name="chevron" size={16}/></button>}>
      <DeviceTable devices={devices.slice(0,5)}/>
    </Panel>
  </>;
}

function DevicesPage({ devices }) {
  return <><div className="intro-bar"><div><div className="eyebrow">FLEET MONITORING</div><h1>Devices</h1><p>View every device with at least one uploaded access event.</p></div><span className="soft-badge"><Icon name="monitor" size={16}/>{number(devices.length)} devices</span></div>
    <Panel title="Agent devices" subtitle="Results from /api/admin/summary"><DeviceTable devices={devices} showSearch/></Panel>
    <div className="info-banner"><Icon name="info" size={18}/><p><strong>Device availability:</strong> This endpoint only lists devices that have recorded events. It does not report online/offline state, agent heartbeats, or per-device snapshots.</p></div>
  </>;
}

const FEATURE_INFO = {
  events: { heading: 'Access events', kicker: 'SECURITY TELEMETRY', icon: 'activity', description: 'Explore each login, failed login, account change and privilege event.', need: 'GET /api/admin/events', fields: 'event_uid, device_id, event_id, occurred_at_utc, username, event_category', next: 'Your backend currently ingests raw events, but exposes only aggregate device counts to admin users.' },
  accounts: { heading: 'Accounts & roles', kicker: 'IDENTITIES', icon: 'users', description: 'Inspect local accounts, groups and privileged memberships collected by agents.', need: 'GET /api/admin/snapshots/latest', fields: 'device_id, collected_at_utc, accounts, groups', next: 'The API stores account snapshots but currently provides only the total snapshot count.' },
  reviews: { heading: 'Access reviews', kicker: 'ACCESS GOVERNANCE', icon: 'clipboard', description: 'Review risky privileges, assign owners and track approval decisions.', need: 'Review workflow API + database tables', fields: 'review_id, device_id, identity, entitlement, reviewer, decision, status', next: 'The current MVP backend has no review workflow or risk recommendation endpoint yet.' },
};
function PlannedPage({ id, goTo }) {
  const info = FEATURE_INFO[id];
  return <><div className="intro-bar"><div><div className="eyebrow">{info.kicker}</div><h1>{info.heading}</h1><p>{info.description}</p></div><span className="soft-badge"><Icon name="info" size={16}/> API required</span></div>
    <Panel className="feature-panel"><div className="feature-layout"><EmptyGraphic icon={info.icon}/><div><span className="section-kicker">NEXT INTEGRATION</span><h2>Connect the detailed data endpoint</h2><p>{info.next}</p><div className="integration-spec"><div><span>Required endpoint / capability</span><code>{info.need}</code></div><div><span>Suggested response fields</span><code>{info.fields}</code></div></div><button className="secondary-button" onClick={()=>goTo('overview')}><Icon name="arrow" size={17}/> Return to overview</button></div></div></Panel>
  </>;
}
function ReportsPage({ summary, devices }) {
  const downloadJson=()=>saveTextFile(JSON.stringify(summary,null,2),`accessreview-summary-${new Date().toISOString().slice(0,10)}.json`,'application/json');
  const downloadCsv=()=>saveTextFile(makeCsv(devices),`accessreview-devices-${new Date().toISOString().slice(0,10)}.csv`,'text/csv;charset=utf-8');
  return <><div className="intro-bar"><div><div className="eyebrow">AUDIT EXPORTS</div><h1>Reports</h1><p>Export the actual summary data currently available from the API.</p></div></div>
    <div className="report-grid"><div className="report-card"><span className="report-icon"><Icon name="file" size={25}/></span><h2>Summary JSON</h2><p>Complete response from the authenticated summary endpoint, including snapshot count and device totals.</p><button className="secondary-button" onClick={downloadJson}><Icon name="download" size={17}/> Download JSON</button></div>
    <div className="report-card"><span className="report-icon alternate"><Icon name="chart" size={25}/></span><h2>Device events CSV</h2><p>A spreadsheet-ready export listing device IDs, cumulative event counts and last recorded events.</p><button className="secondary-button" onClick={downloadCsv}><Icon name="download" size={17}/> Download CSV</button></div></div>
    <div className="info-banner"><Icon name="info" size={18}/><p><strong>Audit-ready reporting requires more data.</strong> These exports contain aggregate information only. Individual event logs, entitlement histories and reviewer decisions need additional authenticated backend endpoints.</p></div>
  </>;
}
function SettingsPage({ summary, onLogout, refresh }) {
  return <><div className="intro-bar"><div><div className="eyebrow">WORKSPACE</div><h1>Settings</h1><p>Connection details and session controls for this console.</p></div></div>
    <div className="settings-grid"><Panel title="API connection" subtitle="Secure same-origin proxy"><div className="setting-row"><span>API summary path</span><code>/api/admin/summary</code></div><div className="setting-row"><span>Refresh interval</span><strong>30 seconds</strong></div><div className="setting-row"><span>Last generated</span><strong>{fullDate(summary.generated_at_utc)}</strong></div><div className="setting-row"><span>Authentication</span><strong>Admin token header</strong></div></Panel>
    <Panel title="Session & security" subtitle="Protecting your workspace"><div className="security-list"><div><Icon name="check" size={18}/><span>Admin token retained only in application memory</span></div><div><Icon name="check" size={18}/><span>No credentials committed to frontend source</span></div><div><Icon name="check" size={18}/><span>Production proxy forwards only the permitted read endpoint</span></div></div><div className="settings-actions"><button className="secondary-button" onClick={refresh}><Icon name="refresh" size={17}/> Refresh now</button><button className="danger-button" onClick={onLogout}><Icon name="logout" size={17}/> Disconnect</button></div></Panel></div>
  </>;
}

function Dashboard({ summary, onLogout, onRefresh, refreshing, refreshError, lastRefreshed }) {
  const [page, setPage] = useState('overview');
  const [menuOpen, setMenuOpen] = useState(false);
  const devices = useMemo(()=>Array.isArray(summary.devices) ? summary.devices.map((dev)=>({device_id:String(dev.device_id || 'Unknown'),event_count:Number(dev.event_count)||0,last_event_utc:dev.last_event_utc || null})) : [],[summary]);
  const pageTitle = NAV.find((item)=>item.id===page)?.text || (page === 'settings' ? 'Settings':'Overview');
  const navigate=(next)=>{setPage(next);setMenuOpen(false);window.scrollTo({top:0,behavior:'smooth'});};
  return <div className="app-shell">
    {menuOpen && <button className="mobile-overlay" onClick={()=>setMenuOpen(false)} aria-label="Close menu"/>}
    <aside className={`sidebar ${menuOpen?'sidebar-open':''}`}>
      <div className="sidebar-brand"><Brand /><button className="menu-close" onClick={()=>setMenuOpen(false)} aria-label="Close navigation"><Icon name="close" size={20}/></button></div>
      <div className="workspace-chip"><span className="workspace-avatar">A</span><div><strong>AccessReview</strong><small>Enterprise workspace</small></div><Icon name="chevron" size={17}/></div>
      <nav className="sidebar-nav" aria-label="Primary navigation"><div className="nav-label">WORKSPACE</div>
        {NAV.slice(0,2).map((nav)=><button key={nav.id} className={`nav-item ${page===nav.id?'active':''}`} onClick={()=>navigate(nav.id)}><Icon name={nav.icon} size={19}/><span>{nav.text}</span>{page===nav.id && <span className="nav-active-dot"/>}</button>)}
        <div className="nav-label section-spacer">ACCESS GOVERNANCE</div>
        {NAV.slice(2).map((nav)=><button key={nav.id} className={`nav-item ${page===nav.id?'active':''}`} onClick={()=>navigate(nav.id)}><Icon name={nav.icon} size={19}/><span>{nav.text}</span>{page===nav.id && <span className="nav-active-dot"/>}</button>)}
        <div className="nav-label section-spacer">PREFERENCES</div>
        <button className={`nav-item ${page==='settings'?'active':''}`} onClick={()=>navigate('settings')}><Icon name="settings" size={19}/><span>Settings</span></button>
      </nav>
      <div className="sidebar-footer"><div className="sidebar-health"><span className="pulse-dot"/><div><strong>API connected</strong><small>Summary available</small></div></div><button className="sidebar-logout" onClick={onLogout}><Icon name="logout" size={17}/> Disconnect <Icon name="chevron" size={15}/></button></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="top-left"><button className="mobile-menu" onClick={()=>setMenuOpen(true)} aria-label="Open navigation"><Icon name="menu" size={23}/></button><div className="breadcrumb">Workspace <Icon name="chevron" size={15}/> <strong>{pageTitle}</strong></div></div><div className="top-actions"><span className="top-live"><span className="pulse-dot"/> Synced {relativeDate(lastRefreshed)}</span><IconButton icon="refresh" title="Refresh data" onClick={onRefresh} disabled={refreshing}/><span className="top-divider"/><div className="profile-avatar" title="Admin session">AD</div></div></header>
      <div className="page-content">
        {refreshError && <div className="refresh-warning" role="alert"><Icon name="alert" size={18}/><div><strong>Refresh failed.</strong> {refreshError} Showing the last successful response.</div><button onClick={onRefresh}>Try again</button></div>}
        {page==='overview' && <Overview summary={summary} devices={devices} goTo={navigate}/>}
        {page==='devices' && <DevicesPage devices={devices}/>}
        {FEATURE_INFO[page] && <PlannedPage id={page} goTo={navigate}/>}
        {page==='reports' && <ReportsPage devices={devices} summary={summary}/>}
        {page==='settings' && <SettingsPage summary={summary} onLogout={onLogout} refresh={onRefresh}/>}
        <footer className="page-footer"><span>© {new Date().getFullYear()} AccessReviewAgent</span><span>Prototype console · Read-only administrative view</span></footer>
      </div>
    </main>
  </div>;
}

export default function App() {
  const [token, setToken] = useState('');
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [refreshError, setRefreshError] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const getSummary = useCallback(async (secret) => {
    const response = await fetch('/api/admin/summary', {
      method: 'GET',
      headers: { 'X-Admin-Token': secret, 'Accept': 'application/json' },
      cache: 'no-store',
      signal: AbortSignal.timeout(20000),
    });
    if (response.status === 401 || response.status === 403) throw new Error('Invalid admin token. Check ADMIN_API_TOKEN in Coolify.');
    if (!response.ok) throw new Error(`API returned HTTP ${response.status}. Verify the backend and proxy.`);
    const data = await response.json();
    if (!data || !Array.isArray(data.devices) || typeof data.snapshots !== 'number') throw new Error('Unexpected API response. Check /api/admin/summary.');
    return data;
  }, []);

  const connect = async (enteredToken) => {
    if (!enteredToken.trim() || loading) return;
    setLoading(true);
    setError('');
    try {
      const data = await getSummary(enteredToken.trim());
      setSummary(data);
      setToken(enteredToken.trim());
      setLastRefreshed(new Date().toISOString());
    } catch (err) {
      setError(err?.message === 'The operation was aborted due to timeout' ? 'Connection timed out. Check your backend.' : err?.message || 'Could not reach the API.');
    } finally {setLoading(false);}
  };
  const refresh = useCallback(async (secret=token) => {
    if (!secret) return;
    setRefreshing(true);
    try {
      const data = await getSummary(secret);
      setSummary(data);
      setRefreshError('');
      setLastRefreshed(new Date().toISOString());
    } catch (err) {
      setRefreshError(err?.message || 'Unable to refresh.');
    } finally {setRefreshing(false);}
  }, [token, getSummary]);
  useEffect(() => {
    if (!token) return;
    const timer = window.setInterval(() => refresh(token), 30000);
    return () => window.clearInterval(timer);
  }, [token, refresh]);
  const logout = () => {setToken('');setSummary(null);setError('');setRefreshError('');};
  if (!token || !summary) return <Login onConnect={connect} loading={loading} error={error}/>;
  return <Dashboard summary={summary} onLogout={logout} onRefresh={()=>refresh()} refreshing={refreshing} refreshError={refreshError} lastRefreshed={lastRefreshed}/>;
}
