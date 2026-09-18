// raNora wireframe screens — keyed by route, returns HTML strings.
// All static data, no fetch. Routing handled in app.js.

window.SCREENS = {};

/* =============================================================
   DASHBOARD — branches on role: user vs power
============================================================= */
SCREENS.home = () => (window.__getRole && window.__getRole() === "power")
  ? SCREENS_homePower()
  : SCREENS_homeUser();

/* ----- USER-FIRST HOME ----- */
function SCREENS_homeUser(){ return `
<div class="screen is-active" data-route="home">
  <div class="home-hero">
    <span class="eyebrow">27 April 2026 · Tuesday</span>
    <h1 class="display mt-12">Good afternoon, <em>Chandan.</em></h1>
    <p class="lede mt-12">Ask any of your agents. Pick up a thread you left earlier. Or jump straight to a coverage map.</p>

    <div class="home-compose">
      <div class="home-compose__pick">
        <span class="muted mono home-compose__label">Ask</span>
        <button class="home-compose__agent">
          <span class="dotcap dotcap--emerald"></span>
          <span>Asset DB Agent</span>
          <svg viewBox="0 0 16 16" width="12" height="12"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
        </button>
      </div>
      <textarea class="home-compose__input" rows="2" placeholder="What do you need to do today?  (e.g. “Audit antenna heights for cells in Lisbon-East.”)"></textarea>
      <div class="home-compose__foot">
        <div class="row gap-6">
          <button class="compose-tool"><svg viewBox="0 0 14 14" width="11" height="11"><path d="M9 3l-5 5a2 2 0 0 0 3 3l5-5a4 4 0 0 0-6-6L1 5" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>Attach</button>
          <button class="compose-tool">@ Cells</button>
          <button class="compose-tool">@ Site</button>
          <button class="compose-tool">@ Polygon</button>
        </div>
        <div class="row gap-8">
          <span class="muted mono" style="font-size:10.5px">⌘ ↵ to send</span>
          <button class="btn btn--primary btn--sm">Ask</button>
        </div>
      </div>
    </div>

    <div class="home-suggest">
      <span class="muted mono home-suggest__label">try</span>
      <button class="home-suggest__chip">Audit antenna heights · Lisbon-East</button>
      <button class="home-suggest__chip">Cells with PCI 211</button>
      <button class="home-suggest__chip">Run RSRP coverage on my selected cells</button>
      <button class="home-suggest__chip">Tilt mismatches in last 24 h</button>
      <button class="home-suggest__chip">Find cells with TTI bundling enabled</button>
    </div>
  </div>

  <div class="rule"><span class="rule__index">§ 01</span> Pick up where you left off</div>

  <div class="grid grid-3 mb-24">
    ${[
      {title:"TTI bundling for cell 1.2.840.0.421",agent:"Asset DB",accent:"emerald",time:"2 min ago",preview:"…confirmed: TTI bundling enabled, antenna height 28.5 m. No discrepancies on this cell."},
      {title:"RSRP coverage · Lisbon-East",agent:"Coverage",accent:"cobalt",time:"17 min ago",preview:"Map ready · 4 of 12 cells rendered. 87.4 % above –105 dBm threshold."},
      {title:"Tilt mismatch · cell_lte vs physical antenna",agent:"Asset DB",accent:"emerald",time:"1 hour ago",preview:"3 cells reported tilt delta &gt; 1.5°. Want me to stage EDS fixes?"},
    ].map(t=>`
      <a href="#agent/${t.agent==='Coverage'?'coverage':'asset-db'}" class="thread-card">
        <div class="row row--between mb-8">
          <span class="tag tag--${t.accent}">${t.agent}</span>
          <span class="muted mono" style="font-size:10.5px">${t.time}</span>
        </div>
        <div class="thread-card__title">${t.title}</div>
        <div class="thread-card__preview">${t.preview}</div>
        <div class="thread-card__foot"><span class="muted mono" style="font-size:10px">↑ continue thread</span></div>
      </a>
    `).join("")}
  </div>

  <div class="rule"><span class="rule__index">§ 02</span> Your agents</div>

  <div class="grid grid-2 mb-24">
    <a href="#agent/asset-db" class="agent-card agent-card--simple" data-accent="emerald">
      <div class="row gap-12">
        <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><ellipse cx="10" cy="5" rx="6" ry="2.2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M4 5v10c0 1.2 2.7 2.2 6 2.2s6-1 6-2.2V5" fill="none" stroke="currentColor" stroke-width="1.4"/></svg></div>
        <div class="flex-1">
          <div class="agent-card__title">Asset DB <em>Agent</em></div>
          <div class="agent-card__sub">Ask anything about your cells, sites, antennas. Run audits. Stage fixes for review.</div>
        </div>
        <span class="status status--ok">ready</span>
      </div>
      <div class="row gap-8 mt-12">
        <button class="btn btn--sm btn--ghost">New thread</button>
        <button class="btn btn--sm btn--ghost">Recent (23)</button>
      </div>
    </a>

    <a href="#agent/coverage" class="agent-card agent-card--simple" data-accent="cobalt">
      <div class="row gap-12">
        <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><circle cx="10" cy="10" r="2" fill="currentColor"/><path d="M5.5 10a4.5 4.5 0 0 1 9 0M3 10a7 7 0 0 1 14 0" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg></div>
        <div class="flex-1">
          <div class="agent-card__title">Coverage <em>Agent</em></div>
          <div class="agent-card__sub">Generate RSRP coverage maps. Compare to baseline. Find gaps.</div>
        </div>
        <span class="status status--running">1 job running</span>
      </div>
      <div class="row gap-8 mt-12">
        <button class="btn btn--sm btn--ghost">Run coverage</button>
        <button class="btn btn--sm btn--ghost">My maps (12)</button>
      </div>
    </a>

    <a href="#agent/cm" class="agent-card agent-card--simple" data-accent="amber">
      <div class="row gap-12">
        <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><circle cx="10" cy="10" r="2.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M10 2v4m0 8v4M2 10h4m8 0h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg></div>
        <div class="flex-1">
          <div class="agent-card__title">CM <em>Agent</em></div>
          <div class="agent-card__sub">Review and approve cell-on-cell remediations.</div>
        </div>
        <span class="status status--pending">3 waiting on you</span>
      </div>
      <div class="row gap-8 mt-12">
        <button class="btn btn--sm btn--accent">Review queue</button>
      </div>
    </a>

    <a href="#agent/ztp" class="agent-card agent-card--simple" data-accent="violet">
      <div class="row gap-12">
        <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><path d="M3 16h14M5 16V8l5-4 5 4v8M8 16v-4h4v4" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg></div>
        <div class="flex-1">
          <div class="agent-card__title">ZTP <em>Agent</em></div>
          <div class="agent-card__sub">Track new sites coming online. 5 in flight today.</div>
        </div>
        <span class="status status--running">5 in flight</span>
      </div>
      <div class="row gap-8 mt-12">
        <button class="btn btn--sm btn--ghost">My sites</button>
      </div>
    </a>
  </div>

  <div class="rule"><span class="rule__index">§ 03</span> For you</div>

  <div class="grid grid-2">
    <div class="card">
      <div class="row row--between mb-16">
        <div class="h3">Waiting on you</div>
        <span class="muted mono" style="font-size:10.5px">3 items</span>
      </div>
      <div class="col gap-8">
        <div class="todo-row">
          <span class="dotcap dotcap--amber"></span>
          <div class="flex-1">
            <div class="todo-row__title">Confirm CoC pair · A4231 ↔ A4233</div>
            <div class="muted mono" style="font-size:10.5px">CM Agent · auto-detected 6h 02m ago</div>
          </div>
          <a href="#agent/cm" class="btn btn--sm btn--accent">Review</a>
        </div>
        <div class="todo-row">
          <span class="dotcap dotcap--cobalt"></span>
          <div class="flex-1">
            <div class="todo-row__title">3 EDS fixes staged for review</div>
            <div class="muted mono" style="font-size:10.5px">Asset DB · tilt deltas in cluster .422</div>
          </div>
          <a href="#agent/asset-db" class="btn btn--sm btn--ghost">Open</a>
        </div>
        <div class="todo-row">
          <span class="dotcap dotcap--violet"></span>
          <div class="flex-1">
            <div class="todo-row__title">Approve change window · 02:00–04:00 UTC</div>
            <div class="muted mono" style="font-size:10.5px">ZTP · 5 sites pending bring-up</div>
          </div>
          <a href="#agent/ztp" class="btn btn--sm btn--ghost">Open</a>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="row row--between mb-16">
        <div class="h3">Your workspace</div>
        <span class="muted mono" style="font-size:10.5px">NOS Portugal</span>
      </div>
      <div class="grid grid-2 gap-12">
        <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">CELLS IN SCOPE</div><div class="h3" style="font-size:18px;margin-top:4px">3 128</div><div class="muted" style="font-size:11px">LTE 2 887 · NR 241</div></div>
        <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">SITES IN SCOPE</div><div class="h3" style="font-size:18px;margin-top:4px">847</div><div class="muted" style="font-size:11px">Lisbon · Porto · Coimbra</div></div>
        <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">YOUR THREADS</div><div class="h3" style="font-size:18px;margin-top:4px">23</div><div class="muted" style="font-size:11px">this week</div></div>
        <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">YOUR FIXES (MTD)</div><div class="h3" style="font-size:18px;margin-top:4px;color:var(--emerald)">14</div><div class="muted" style="font-size:11px">applied · 0 reverted</div></div>
      </div>
    </div>
  </div>
</div>
`; }

/* ----- POWER-USER HOME (original dense version) ----- */
function SCREENS_homePower(){ return `
<div class="screen is-active" data-route="home">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Operator Console · 27 April 2026</span>
      <h1 class="display mt-12">Good afternoon, Chandan.<br/><em>Network is calm.</em></h1>
      <p class="lede mt-16">Four agents online. Two threads waiting on review. CM Agent flagged 3 incidents in the past hour — none autonomous yet, all pending operator confirm.</p>
    </div>
    <div class="col gap-8" style="align-items:flex-end">
      <div class="row gap-8">
        <button class="btn btn--ghost"><span class="kbd">G</span><span class="kbd">D</span><span style="margin-left:6px">DB Agent</span></button>
        <button class="btn btn--primary">
          <svg viewBox="0 0 16 16" width="14" height="14"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          New conversation
        </button>
      </div>
      <span class="muted mono" style="font-size:11px">Last sync 14:21:08 · grgd-scm-vm01</span>
    </div>
  </div>

  <!-- KPI row -->
  <div class="grid grid-4 mb-24">
    <div class="stat">
      <span class="card__corner">01 / 04</span>
      <span class="stat__label">Active sites</span>
      <span class="stat__value">4,281</span>
      <span class="stat__delta stat__delta--up">▲ 12 vs yesterday · LTE 3,890 · NR 391</span>
      <svg class="spark spark--signal" viewBox="0 0 100 28" preserveAspectRatio="none"><path d="M0,20 L8,18 L16,21 L24,16 L32,17 L40,12 L48,14 L56,9 L64,11 L72,7 L80,9 L88,5 L96,8 L100,6"/></svg>
    </div>
    <div class="stat">
      <span class="card__corner">02 / 04</span>
      <span class="stat__label">Open incidents</span>
      <span class="stat__value" style="color:var(--amber)">7</span>
      <span class="stat__delta">CoC pairs 3 · KPI deviation 2 · ZTP failed 2</span>
      <svg class="spark spark--amber" viewBox="0 0 100 28" preserveAspectRatio="none"><path d="M0,12 L10,15 L20,11 L30,18 L40,14 L50,9 L60,16 L70,10 L80,13 L90,8 L100,11"/></svg>
    </div>
    <div class="stat">
      <span class="card__corner">03 / 04</span>
      <span class="stat__label">Audit fixes (24h)</span>
      <span class="stat__value">47</span>
      <span class="stat__delta stat__delta--up">▲ 18 · 41 auto · 6 manual review</span>
      <svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none"><path d="M0,22 L12,20 L24,18 L36,12 L48,15 L60,8 L72,10 L84,6 L96,4 L100,3"/></svg>
    </div>
    <div class="stat">
      <span class="card__corner">04 / 04</span>
      <span class="stat__label">LLM spend (MTD)</span>
      <span class="stat__value">$184<span style="font-size:18px;color:var(--text-3)">.22</span></span>
      <span class="stat__delta stat__delta--up">▼ 12% · Qwen3 / Gemini Flash</span>
      <svg class="spark spark--emerald" viewBox="0 0 100 28" preserveAspectRatio="none"><path d="M0,8 L10,9 L20,11 L30,13 L40,12 L50,15 L60,17 L70,16 L80,19 L90,18 L100,21"/></svg>
    </div>
  </div>

  <div class="rule"><span class="rule__index">§ 01</span> Agents at a glance</div>

  <!-- Agent cards -->
  <div class="grid grid-2 mb-24">
    <a href="#agent/asset-db" class="agent-card" data-accent="emerald">
      <div class="agent-card__head">
        <div class="row gap-12">
          <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><ellipse cx="10" cy="5" rx="6" ry="2.2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M4 5v10c0 1.2 2.7 2.2 6 2.2s6-1 6-2.2V5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M4 10c0 1.2 2.7 2.2 6 2.2s6-1 6-2.2" fill="none" stroke="currentColor" stroke-width="1.4"/></svg></div>
          <div>
            <div class="agent-card__title">Asset DB <em>Agent</em></div>
            <div class="agent-card__sub">Auditor · Implementor · EDS Fixer</div>
          </div>
        </div>
        <span class="status status--idle">idle · v2.4.1</span>
      </div>
      <div class="agent-card__rows">
        <div class="agent-card__row"><span class="agent-card__row-label">Threads today</span><span class="agent-card__row-value">23</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">P95 latency</span><span class="agent-card__row-value">1.4 s</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Tools</span><span class="agent-card__row-value">RAG · Audit · Discrepancy · Fixer</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Recursion limit</span><span class="agent-card__row-value mono">4</span></div>
      </div>
      <div class="agent-card__foot">
        <span class="muted mono" style="font-size:11px">Last query · 02:17 ago · "TTI bundling for cell 1.2.840…"</span>
        <span class="tag tag--emerald">ACTIVE</span>
      </div>
    </a>

    <a href="#agent/coverage" class="agent-card" data-accent="cobalt">
      <div class="agent-card__head">
        <div class="row gap-12">
          <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><circle cx="10" cy="10" r="2" fill="currentColor"/><path d="M5.5 10a4.5 4.5 0 0 1 9 0M3 10a7 7 0 0 1 14 0" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg></div>
          <div>
            <div class="agent-card__title">Coverage <em>Agent</em></div>
            <div class="agent-card__sub">Map generation · ASP candidates</div>
          </div>
        </div>
        <span class="status status--running">running · 1 job</span>
      </div>
      <div class="agent-card__rows">
        <div class="agent-card__row"><span class="agent-card__row-label">Maps generated</span><span class="agent-card__row-value">312</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">ASP sessions</span><span class="agent-card__row-value">9 open</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Tech</span><span class="agent-card__row-value">LTE · NR</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Last run</span><span class="agent-card__row-value mono">14:18:44</span></div>
      </div>
      <div class="agent-card__foot">
        <span class="muted mono" style="font-size:11px">Computing RSRP · Lisbon East · 4 of 12 cells</span>
        <span class="tag tag--cobalt">ACTIVE</span>
      </div>
    </a>

    <a href="#agent/cm" class="agent-card" data-accent="amber">
      <div class="agent-card__head">
        <div class="row gap-12">
          <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><path d="M10 2v4m0 8v4M2 10h4m8 0h4M4.5 4.5l2.8 2.8m5.4 5.4l2.8 2.8m0-11l-2.8 2.8M7.3 12.7l-2.8 2.8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="10" cy="10" r="2.5" fill="none" stroke="currentColor" stroke-width="1.4"/></svg></div>
          <div>
            <div class="agent-card__title">CM <em>Agent</em></div>
            <div class="agent-card__sub">Cell-on-Cell · alarm-to-remediation</div>
          </div>
        </div>
        <span class="status status--pending">3 pending review</span>
      </div>
      <div class="agent-card__rows">
        <div class="agent-card__row"><span class="agent-card__row-label">Mode</span><span class="agent-card__row-value">DRY-RUN</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Stable window</span><span class="agent-card__row-value mono">06:00:00</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Resolved (24h)</span><span class="agent-card__row-value">14</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Vendor</span><span class="agent-card__row-value">Huawei iMaster NCE</span></div>
      </div>
      <div class="agent-card__foot">
        <span class="muted mono" style="font-size:11px">Newest pair · node-A4231 ↔ node-A4233 · severity 5</span>
        <span class="tag tag--amber">REVIEW</span>
      </div>
    </a>

    <a href="#agent/ztp" class="agent-card" data-accent="violet">
      <div class="agent-card__head">
        <div class="row gap-12">
          <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><path d="M3 16h14M5 16V8l5-4 5 4v8M8 16v-4h4v4" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg></div>
          <div>
            <div class="agent-card__title">ZTP <em>Agent</em></div>
            <div class="agent-card__sub">Zero-Touch Provisioning · Day-0 / Day-1</div>
          </div>
        </div>
        <span class="status status--running">5 sites bringing up</span>
      </div>
      <div class="agent-card__rows">
        <div class="agent-card__row"><span class="agent-card__row-label">Day-0 P50</span><span class="agent-card__row-value mono">7m 12s</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Day-1 P50</span><span class="agent-card__row-value mono">26m 04s</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">Auto-rollback</span><span class="agent-card__row-value">2 today</span></div>
        <div class="agent-card__row"><span class="agent-card__row-label">PCI auto-resolve</span><span class="agent-card__row-value">94.6 %</span></div>
      </div>
      <div class="agent-card__foot">
        <span class="muted mono" style="font-size:11px">Active · enb-LX-0421 · stage Day-1 · KPI watch</span>
        <span class="tag tag--violet">PILOT</span>
      </div>
    </a>
  </div>

  <div class="rule"><span class="rule__index">§ 02</span> Live activity</div>

  <div class="grid" style="grid-template-columns: 2fr 1fr; gap:16px">
    <div class="card" style="padding:0">
      <div class="row row--between" style="padding:16px 20px;border-bottom:1px solid var(--line)">
        <div>
          <div class="h3">Activity feed</div>
          <span class="muted mono" style="font-size:11px">tail -f · per-agent stream</span>
        </div>
        <div class="row gap-8">
          <button class="btn btn--sm btn--ghost">All agents</button>
          <button class="btn btn--sm btn--ghost">Last 24h</button>
        </div>
      </div>
      <table class="tbl">
        <thead><tr><th>Time</th><th>Agent</th><th>Event</th><th>Subject</th><th>Outcome</th></tr></thead>
        <tbody>
          <tr><td class="mono">14:21:08</td><td><span class="tag tag--emerald">Asset DB</span></td><td>Audit chain completed</td><td class="mono">cell_iid · 1.2.840.0.421</td><td><span class="status status--ok">ok · 2 fixes queued</span></td></tr>
          <tr><td class="mono">14:18:44</td><td><span class="tag tag--cobalt">Coverage</span></td><td>Polygon submitted</td><td class="mono">Lisbon-East · 12 cells LTE</td><td><span class="status status--running">running · 33 %</span></td></tr>
          <tr><td class="mono">14:11:02</td><td><span class="tag tag--amber">CM · CoC</span></td><td>Pair stable for 6h</td><td class="mono">node-A4231 ↔ A4233</td><td><span class="status status--pending">awaiting confirm</span></td></tr>
          <tr><td class="mono">14:04:21</td><td><span class="tag tag--violet">ZTP</span></td><td>Day-1 stage 4 / 4</td><td class="mono">enb-LX-0421</td><td><span class="status status--ok">KPI watch</span></td></tr>
          <tr><td class="mono">13:58:55</td><td><span class="tag tag--emerald">Asset DB</span></td><td>SQL retry · column hint</td><td class="mono">ttibundling → act_tti_bundling</td><td><span class="status status--ok">resolved · 1 retry</span></td></tr>
          <tr><td class="mono">13:51:30</td><td><span class="tag tag--violet">ZTP</span></td><td>Day-0 done</td><td class="mono">gnb-PT-0094</td><td><span class="status status--ok">8m 41s</span></td></tr>
          <tr><td class="mono">13:42:11</td><td><span class="tag tag--amber">CM · CoC</span></td><td>Auto-rollback</td><td class="mono">candidate-1748</td><td><span class="status status--error">KPI regressed</span></td></tr>
        </tbody>
      </table>
    </div>

    <div class="col gap-16">
      <div class="card">
        <div class="row row--between"><div class="h3">System pulse</div><span class="muted mono" style="font-size:10px">5s ago</span></div>
        <div class="col gap-8 mt-16">
          <div class="row row--between"><span class="muted">Postgres</span><span class="mono" style="color:var(--emerald)">● 4ms · pool 8/40</span></div>
          <div class="row row--between"><span class="muted">Redis</span><span class="mono" style="color:var(--emerald)">● 0.6ms</span></div>
          <div class="row row--between"><span class="muted">Phoenix tracing</span><span class="mono" style="color:var(--emerald)">● 312 spans/min</span></div>
          <div class="row row--between"><span class="muted">Keycloak</span><span class="mono" style="color:var(--emerald)">● 47 sessions</span></div>
          <div class="row row--between"><span class="muted">Huawei NCE (sim)</span><span class="mono" style="color:var(--amber)">● simulator</span></div>
        </div>
      </div>

      <div class="card">
        <div class="h3 mb-8">Operator todos</div>
        <div class="col gap-8">
          <div class="row gap-8" style="padding:8px;border-radius:8px;background:var(--surface-2)">
            <span class="dotcap dotcap--amber"></span>
            <div class="flex-1">
              <div style="font-weight:500">Confirm CoC pair · A4231 ↔ A4233</div>
              <div class="muted mono" style="font-size:10.5px">CM Agent · 3 minutes</div>
            </div>
          </div>
          <div class="row gap-8" style="padding:8px;border-radius:8px;background:var(--surface-2)">
            <span class="dotcap dotcap--cobalt"></span>
            <div class="flex-1">
              <div style="font-weight:500">Review 3 EDS fixes</div>
              <div class="muted mono" style="font-size:10.5px">Asset DB · staged</div>
            </div>
          </div>
          <div class="row gap-8" style="padding:8px;border-radius:8px;background:var(--surface-2)">
            <span class="dotcap dotcap--violet"></span>
            <div class="flex-1">
              <div style="font-weight:500">Approve change window · 02:00–04:00 UTC</div>
              <div class="muted mono" style="font-size:10.5px">ZTP · 5 sites</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
`; }

/* =============================================================
   ASSET DB AGENT
============================================================= */
SCREENS["agent/asset-db"] = () => `
<div class="screen is-active" data-route="agent/asset-db">
  <div class="row row--between mb-16">
    <div>
      <span class="eyebrow">Agent · 01 / 04</span>
      <h1 class="h2 mt-8">Asset DB Agent <em>· Auditor</em></h1>
      <span class="muted user-only" style="font-size:12px">Ask anything about your cells, sites, antennas. Run audits. Stage fixes for review.</span>
      <span class="muted mono power-only" style="font-size:11px">v2.4.1 · qwen3-32b (sql-gen) · qwen3-coder-next (executor) · qwen3.5-flash (summary)</span>
    </div>
    <div class="row gap-8">
      <button class="btn btn--ghost"><svg viewBox="0 0 16 16" width="13" height="13"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>New thread</button>
      <button class="btn btn--ghost">Export</button>
      <button class="btn btn--accent power-only">Configure</button>
    </div>
  </div>

  <div class="kpi-bar mb-16 power-only">
    <div class="kpi-bar__item"><span class="kpi-bar__label">Threads today</span><span class="kpi-bar__value">23</span></div>
    <div class="kpi-bar__sep"></div>
    <div class="kpi-bar__item"><span class="kpi-bar__label">Tool calls (24h)</span><span class="kpi-bar__value">412</span></div>
    <div class="kpi-bar__sep"></div>
    <div class="kpi-bar__item"><span class="kpi-bar__label">Avg latency</span><span class="kpi-bar__value">1.4<span style="font-size:14px;color:var(--text-3)">s</span></span></div>
    <div class="kpi-bar__sep"></div>
    <div class="kpi-bar__item"><span class="kpi-bar__label">Tokens (MTD)</span><span class="kpi-bar__value">11.8<span style="font-size:14px;color:var(--text-3)">M</span></span></div>
    <div class="kpi-bar__sep"></div>
    <div class="kpi-bar__item"><span class="kpi-bar__label">RLS scope</span><span class="kpi-bar__value" style="font-size:16px">3,128 cells</span></div>
  </div>

  <div class="chat-shell">
    <!-- thread rail -->
    <aside class="chat-rail">
      <div class="chat-rail__head">
        <div class="row gap-8"><span class="h4">Threads</span><span class="tag tag--ghost mono">128</span></div>
        <button class="iconbtn" title="New"><svg viewBox="0 0 16 16" width="14" height="14"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button>
      </div>
      <div class="chat-rail__list">
        ${[
          {t:"TTI bundling for cell 1.2.840…", time:"2m", active:true, n:"4 calls"},
          {t:"Azimuth audit · sites in Porto", time:"21m", n:"audit + fixes"},
          {t:"Tilt mismatch · cell_lte vs physical antenna", time:"1h", n:"discrepancy"},
          {t:"Find all cells with PCI 211", time:"3h", n:"rag"},
          {t:"Site count by region (LTE)", time:"yesterday", n:"rag"},
          {t:"Run EDS fixer for batch 042", time:"yesterday", n:"fixer"},
          {t:"Cross-tech LTE↔NR neighbours", time:"2 days", n:"rag chain"},
          {t:"Height mismatch audit", time:"2 days", n:"audit"},
          {t:"Antenna model drift Q1", time:"3 days", n:"audit · 12 fixes"},
        ].map(x=>`
          <div class="thread-item ${x.active?'is-active':''}">
            <div class="thread-item__title">${x.t}</div>
            <div class="thread-item__meta"><span>${x.n}</span><span>${x.time}</span></div>
          </div>`).join("")}
      </div>
    </aside>

    <!-- main chat -->
    <section class="chat-main">
      <div class="chat-main__head">
        <div>
          <div class="h3">TTI bundling for cell 1.2.840.0.421</div>
          <span class="muted mono" style="font-size:11px">thread_id · 9b4e-c1d2-f8a0 · 4 tool calls · Qwen3-Coder-Next</span>
        </div>
        <div class="row gap-8">
          <button class="btn btn--sm btn--ghost">Rename</button>
          <button class="btn btn--sm btn--ghost">Share</button>
          <button class="btn btn--sm btn--ghost"><svg viewBox="0 0 16 16" width="12" height="12"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M8 5v3l2 1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg> History</button>
        </div>
      </div>
      <div class="chat-main__feed">
        <div class="bubble bubble--user">
          <div class="bubble__role" style="justify-content:flex-end"><span class="bubble__time">14:18:21</span><span>You</span></div>
          <div class="bubble__body">For cell 1.2.840.0.421, what is the value of TTIbundling? Also confirm the antenna height.</div>
        </div>

        <div class="bubble bubble--assistant" style="max-width:88%">
          <div class="bubble__role"><span class="dotcap dotcap--emerald"></span><span>Asset DB Agent</span><span class="bubble__time">14:18:23</span></div>
          <div class="bubble__body">
            <span class="user-only">Looking up TTI bundling and antenna height for cell <span class="mono">1.2.840.0.421</span>…</span>
            <span class="power-only">I'll look this up. The asset database stores TTI bundling on <span class="mono" style="color:var(--signal)">cell_lte.lte_carrierparameters_ttibundlingenabled</span> and antenna height on <span class="mono" style="color:var(--signal)">cell_physical_antenna.height</span> — I'll JOIN on cell_iid and antennadevice_iid.</span>

            <div class="tool-call power-only">
              <div class="tool-call__head">
                <span class="dotcap dotcap--cobalt"></span>
                <span class="tool-call__name">asset_db_rag_tool</span>
                <span class="muted">→ resolved in 0.62 s · 1 row</span>
                <span class="tag tag--signal" style="margin-left:auto">SELECT</span>
              </div>
              <div class="tool-call__body">SELECT  c.cell_iid,
        c.lte_carrierparameters_ttibundlingenabled  AS tti_bundling,
        a.height                                    AS antenna_height_m
FROM cell_lte c
JOIN cell_physical_antenna a USING (cell_iid)
WHERE c.cell_iid = '1.2.840.0.421';</div>
            </div>

            <div class="tool-call power-only">
              <div class="tool-call__head">
                <span class="dotcap dotcap--signal"></span>
                <span class="tool-call__name">audit_engine_tool</span>
                <span class="muted">→ no discrepancies on this cell</span>
              </div>
              <div class="tool-call__body">{ "audited_fields": ["tti_bundling", "antenna_height_m"], "discrepancies": [] }</div>
            </div>

            <div class="tool-call user-only">
              <div class="tool-call__head">
                <span class="dotcap dotcap--cobalt"></span>
                <span style="color:var(--text)">Queried asset DB · 1 cell matched</span>
                <span class="tag tag--emerald" style="margin-left:auto">audit clean</span>
              </div>
            </div>

            <div style="margin-top:14px"><strong>TTI bundling</strong> is <span class="tag tag--signal mono">enabled</span> for this cell. <strong>Antenna height</strong> is <span class="tag tag--cobalt mono">28.5 m</span>. Both values match the planned configuration; no discrepancies.</div>
          </div>
        </div>

        <div class="bubble bubble--user">
          <div class="bubble__role" style="justify-content:flex-end"><span class="bubble__time">14:20:06</span><span>You</span></div>
          <div class="bubble__body">Run the same audit for the rest of the sector — cells .421, .422, .423.</div>
        </div>

        <div class="bubble bubble--assistant" style="max-width:88%">
          <div class="bubble__role"><span class="dotcap dotcap--emerald"></span><span>Asset DB Agent</span><span class="bubble__time">14:20:08</span></div>
          <div class="bubble__body">
            Running batched audit on 3 cells…
            <div class="tool-call">
              <div class="tool-call__head"><span class="dotcap dotcap--amber"></span><span class="tool-call__name">discrepancy_engine_tool</span><span class="muted">→ 1 row out of bound</span></div>
              <div class="tool-call__body">cell_iid 1.2.840.0.422  ·  height_m 31.0  →  planned 28.5  ·  Δ +2.5 m</div>
            </div>
            Cell <span class="mono">.422</span> reports a 2.5 m height delta. Want me to stage an EDS fix?
            <div class="row gap-8 mt-12">
              <button class="btn btn--sm btn--accent">Stage fix</button>
              <button class="btn btn--sm btn--ghost">Show source</button>
              <button class="btn btn--sm btn--ghost">Ignore</button>
            </div>
          </div>
        </div>
      </div>
      <div class="chat-main__compose">
        <div class="compose-box">
          <textarea class="compose-input" rows="2" placeholder="Ask anything · plain English · @cells, @sites, @cmds…"></textarea>
          <div class="compose-row">
            <div class="compose-tools">
              <button class="compose-tool"><svg viewBox="0 0 14 14" width="11" height="11"><path d="M9 3l-5 5a2 2 0 0 0 3 3l5-5a4 4 0 0 0-6-6L1 5" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>Attach</button>
              <button class="compose-tool"><svg viewBox="0 0 14 14" width="11" height="11"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M7 4v3l2 1" stroke="currentColor" stroke-width="1.4"/></svg>History</button>
              <button class="compose-tool">@ Cells</button>
              <button class="compose-tool">@ Site</button>
            </div>
            <div class="row gap-8">
              <span class="muted mono" style="font-size:10px">⌘ ↵ to send</span>
              <button class="btn btn--primary btn--sm">Send</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- inspector -->
    <aside class="right-rail">
      <div class="right-rail__tabs">
        <button class="right-rail__tab is-active">Sources</button>
        <button class="right-rail__tab power-only">Tools</button>
        <button class="right-rail__tab power-only">Trace</button>
      </div>
      <div class="right-rail__body">
        <div class="h4 mb-8">This thread</div>
        <div class="col gap-8">
          <div class="callout callout--signal">
            <strong style="color:var(--signal)">Found a match ·</strong> "TTI bundling" maps to <span class="mono">lte_carrierparameters_ttibundlingenabled</span> on table <span class="mono">cell_lte</span>.
          </div>
          <div class="card card--quiet" style="padding:12px">
            <div class="muted mono" style="font-size:10px">CELLS REFERENCED</div>
            <div class="row gap-6 mt-8" style="flex-wrap:wrap">
              <span class="tag mono">1.2.840.0.421</span><span class="tag mono">.422</span><span class="tag mono">.423</span>
            </div>
          </div>
          <div class="card card--quiet user-only" style="padding:12px">
            <div class="muted mono" style="font-size:10px">YOUR ACTIONS</div>
            <div class="col gap-4 mt-8">
              <button class="btn btn--sm btn--ghost" style="justify-content:flex-start;width:100%">Stage fix on .422</button>
              <button class="btn btn--sm btn--ghost" style="justify-content:flex-start;width:100%">Save to my reports</button>
              <button class="btn btn--sm btn--ghost" style="justify-content:flex-start;width:100%">Share with team</button>
            </div>
          </div>
          <div class="card card--quiet power-only" style="padding:12px">
            <div class="muted mono" style="font-size:10px">SQL · 0.62 s · explain 4ms</div>
            <div class="mono" style="font-size:11.5px;color:var(--text);margin-top:4px;line-height:1.6">SELECT c.cell_iid, c.lte_carrierparameters_ttibundlingenabled AS tti, a.height …</div>
          </div>
          <div class="card card--quiet power-only" style="padding:12px">
            <div class="muted mono" style="font-size:10px">Tables touched</div>
            <div class="row gap-6 mt-8" style="flex-wrap:wrap">
              <span class="tag mono">cell_lte</span><span class="tag mono">cell_physical_antenna</span><span class="tag mono">user_project_config</span>
            </div>
          </div>
          <div class="card card--quiet power-only" style="padding:12px">
            <div class="muted mono" style="font-size:10px">RLS scope</div>
            <div class="mono" style="font-size:11.5px;color:var(--text);margin-top:4px">app_rls_user · 3 128 cells in scope · 1 cell matched</div>
          </div>
          <div class="card card--quiet power-only" style="padding:12px">
            <div class="muted mono" style="font-size:10px">Cost · this thread</div>
            <div class="row row--between mt-4"><span>Tokens</span><span class="mono">14 821</span></div>
            <div class="row row--between"><span>Spend</span><span class="mono">$0.0042</span></div>
          </div>
        </div>
      </div>
    </aside>
  </div>
</div>
`;

/* =============================================================
   COVERAGE AGENT
============================================================= */
/* =============================================================
   CM · CELL-ON-CELL AGENT (incident pipeline)
============================================================= */
SCREENS["agent/cm"] = () => `
<div class="screen is-active" data-route="agent/cm">
  <div class="row row--between mb-16">
    <div>
      <span class="eyebrow">Agent · 03 / 04</span>
      <h1 class="h2 mt-8">CM Agent <em>· Cell-on-Cell remediation</em></h1>
      <span class="muted user-only" style="font-size:12px">Pairs of cells flagged by alarms. Review and approve the proposed fix, or reject.</span>
      <span class="muted mono power-only" style="font-size:11px">v0.4 · Huawei iMaster NCE · alarmId 40012 · stable window 06:00:00</span>
    </div>
    <div class="row gap-8">
      <div class="tri power-only">
        <span class="tri__opt tri__opt--off">OFF</span>
        <span class="tri__opt tri__opt--dry is-on">DRY-RUN</span>
        <span class="tri__opt tri__opt--on">AUTONOMOUS</span>
      </div>
      <button class="btn btn--ghost">Runbook</button>
      <button class="btn btn--primary power-only">New incident</button>
    </div>
  </div>

  <div class="callout callout--amber mb-16 power-only">
    <strong style="color:var(--amber)">Dry-run mode active.</strong> All decisions render previews — no MO XML is dispatched to NCE. Toggle <span class="kbd">CM_AUTONOMOUS_MODE</span> to enable execution. Last flip · operator <strong>biman</strong> · 2026-04-22 09:14.
  </div>

  <div class="callout user-only mb-16">
    <strong>3 pairs are waiting for you.</strong> Each one has been stable for the required 6 hours and the agent has prepared a proposed fix. Approve, reject, or snooze.
  </div>

  <div class="kpi-bar mb-16">
    <div class="kpi-bar__item"><span class="kpi-bar__label">Pending review</span><span class="kpi-bar__value" style="color:var(--amber)">3</span></div>
    <div class="kpi-bar__sep"></div>
    <div class="kpi-bar__item"><span class="kpi-bar__label">Resolved (24h)</span><span class="kpi-bar__value">14</span></div>
    <div class="kpi-bar__sep power-only"></div>
    <div class="kpi-bar__item power-only"><span class="kpi-bar__label">Open incidents</span><span class="kpi-bar__value">7</span></div>
    <div class="kpi-bar__sep power-only"></div>
    <div class="kpi-bar__item power-only"><span class="kpi-bar__label">Auto-rollback (24h)</span><span class="kpi-bar__value" style="color:var(--crimson)">2</span></div>
    <div class="kpi-bar__sep"></div>
    <div class="kpi-bar__item"><span class="kpi-bar__label">Mean time to resolve</span><span class="kpi-bar__value">7m<span style="font-size:14px;color:var(--text-3)"> 11s</span></span></div>
  </div>

  <!-- USER MODE: simple review queue -->
  <div class="user-only">
    <div class="rule"><span class="rule__index">§ 01</span> Waiting for your review</div>
    <div class="grid" style="grid-template-columns:1fr;gap:12px">
      ${[
        {id:"AL-7731",pair:"node-A4231 ↔ node-A4233",stable:"6h 02m",summary:"Suggested fix · adjust PCI on node-A4233 from 209 → 211. Confidence 94 %.",accent:"amber",hot:true},
        {id:"AL-7728",pair:"node-C2014 ↔ node-C2018",stable:"5h 41m",summary:"Suggested fix · adjust root sequence index on node-C2018. Confidence 89 %.",accent:"amber"},
        {id:"AL-7720",pair:"node-D8801 ↔ node-D8809",stable:"4h 18m",summary:"Suggested fix · re-plan neighbour list. Confidence 81 %.",accent:"amber"},
      ].map(r=>`
        <div class="card" style="${r.hot?'border-color:rgba(255,184,77,0.30);':''}">
          <div class="row row--between">
            <div>
              <div class="row gap-8 mb-4"><span class="tag tag--amber mono">${r.id}</span><span class="muted mono" style="font-size:10.5px">stable for ${r.stable}</span></div>
              <div class="h3" style="font-size:16px">${r.pair}</div>
              <div class="muted" style="font-size:13px;margin-top:6px">${r.summary}</div>
            </div>
            <div class="row gap-8">
              <button class="btn btn--sm btn--ghost">Snooze 1h</button>
              <button class="btn btn--sm btn--danger">Reject</button>
              <button class="btn btn--sm btn--accent">Approve</button>
            </div>
          </div>
        </div>
      `).join("")}
    </div>
  </div>

  <!-- POWER MODE: full pipeline -->
  <div class="power-only"><div class="rule"><span class="rule__index">§ 01</span> Pipeline · severity 5 alarms only</div></div>

  <div class="pipeline power-only">
    <div class="pipe-col">
      <div class="pipe-col__head"><span class="pipe-col__title">Detected</span><span class="pipe-col__count">2</span></div>
      ${cmCard("AL-7745","node-A4521 ↔ A4527","2 min · severity 5","cobalt")}
      ${cmCard("AL-7746","node-B0118 ↔ B0119","6 min · severity 5","cobalt")}
    </div>
    <div class="pipe-col">
      <div class="pipe-col__head"><span class="pipe-col__title">Stable · 6h window</span><span class="pipe-col__count">3</span></div>
      ${cmCard("AL-7731","node-A4231 ↔ A4233","stable for 6h 02m","amber",true)}
      ${cmCard("AL-7728","node-C2014 ↔ C2018","stable for 5h 41m","amber")}
      ${cmCard("AL-7720","node-D8801 ↔ D8809","stable for 4h 18m","amber")}
    </div>
    <div class="pipe-col">
      <div class="pipe-col__head"><span class="pipe-col__title">Materialized</span><span class="pipe-col__count">1</span></div>
      ${cmCard("AL-7702","node-E1112 ↔ E1119","CANDIDATE_1 row inserted","violet")}
    </div>
    <div class="pipe-col">
      <div class="pipe-col__head"><span class="pipe-col__title">Dispatched</span><span class="pipe-col__count">1</span></div>
      ${cmCard("AL-7689","node-F4002 ↔ F4007","NCE generateImport · waiting","cobalt")}
    </div>
    <div class="pipe-col">
      <div class="pipe-col__head"><span class="pipe-col__title">Closed (24h)</span><span class="pipe-col__count">14</span></div>
      ${cmCard("AL-7677","node-G6601 ↔ G6608","KPI improved · ✓","emerald")}
      ${cmCard("AL-7672","node-H3401 ↔ H3403","KPI regressed · ↺ rollback","crimson")}
      ${cmCard("AL-7665","node-I0040 ↔ I0044","stable · ✓","emerald")}
    </div>
  </div>

  <div class="rule power-only"><span class="rule__index">§ 02</span> Active incident · AL-7731 <span style="margin-left:8px"><span class="tag tag--amber">awaiting confirm</span></span></div>

  <div class="grid power-only" style="grid-template-columns:1.4fr 1fr;gap:16px">
    <div class="card">
      <div class="row row--between">
        <div>
          <div class="h3">node-A4231 ↔ node-A4233</div>
          <div class="muted mono" style="font-size:11px">candidate-1748 · materialized 14:11:02 · vendor Huawei</div>
        </div>
        <div class="row gap-8">
          <button class="btn btn--sm btn--ghost">Snooze 1h</button>
          <button class="btn btn--sm btn--danger">Reject</button>
          <button class="btn btn--sm btn--accent">Approve dispatch</button>
        </div>
      </div>
      <div class="grid grid-3 mt-16">
        <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">DUPLICATE WINDOW</div><div class="h3" style="font-size:16px;margin-top:4px">passed · 47 unique</div></div>
        <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">STABILITY</div><div class="h3" style="font-size:16px;margin-top:4px">6h 02m</div></div>
        <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">BLAST RADIUS</div><div class="h3" style="font-size:16px;margin-top:4px">2 cells</div></div>
      </div>
      <div class="rule" style="margin:24px 0 12px"><span class="rule__index">→</span> Proposed remediation</div>
      <pre class="mono" style="background:var(--ink);border:1px solid var(--line);border-radius:10px;padding:14px;font-size:11.5px;color:var(--text-2);overflow-x:auto;line-height:1.6">&lt;hua:generateImport target="node-A4233"&gt;
  &lt;mo class="EUtranCellFDD"&gt;
    &lt;attr name="pci"&gt;<span style="color:var(--signal)">211</span>&lt;/attr&gt;
    &lt;attr name="rootSequenceIdx"&gt;<span style="color:var(--signal)">114</span>&lt;/attr&gt;
  &lt;/mo&gt;
&lt;/hua:generateImport&gt;</pre>
      <div class="callout callout--signal mt-12"><strong>Confidence ·</strong> 94 % · matches 31 historical pairs in workspace · expected resolve in <span class="mono">02:00–04:00 UTC</span> window.</div>
    </div>

    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:16px 18px;border-bottom:1px solid var(--line)">
        <div class="h3">Decision trail</div>
        <span class="muted mono" style="font-size:11px">Phoenix span · 7-segment</span>
      </div>
      <div style="padding:8px 18px 18px">
        ${[
          ["MATERIALIZE","cm_orch.materialize","candidate row inserted · oracle:NIFI.COC_CANDIDATE_1_INSERT","ok","14:11:02"],
          ["ENRICH","cm_agent.enrich","attribute pivot · 4 views queried","ok","14:11:03"],
          ["BUILD_TEMPLATE","cm_agent.build_template","Huawei MO XML rendered","ok","14:11:04"],
          ["GATE","feature_flag.cm_autonomous_mode","DRY-RUN · awaiting operator","wait","14:11:04"],
          ["DISPATCH_TO_ORCH","—","blocked by gate","wait","—"],
          ["POLL_ORCH","—","—","wait","—"],
          ["RECORD","—","—","wait","—"],
        ].map(s=>`
          <div class="row gap-12" style="padding:10px 0;border-bottom:1px solid var(--line)">
            <span class="dotcap ${s[3]==='ok'?'dotcap--emerald':s[3]==='wait'?'dotcap--amber':'dotcap--crimson'}"></span>
            <div class="flex-1">
              <div class="row row--between"><span class="mono" style="font-size:11px;color:var(--text)">${s[0]}</span><span class="muted mono" style="font-size:10px">${s[4]}</span></div>
              <div class="muted mono" style="font-size:10.5px;margin-top:2px">${s[1]} · ${s[2]}</div>
            </div>
          </div>`).join("")}
      </div>
    </div>
  </div>
</div>
`;

function cmCard(id, title, meta, color, active=false){
  return `<div class="pipe-card" style="${active?'border-color:rgba(255,184,77,0.40);box-shadow:0 0 0 1px rgba(255,184,77,0.10);':''}">
    <div class="pipe-card__id">${id}</div>
    <div class="pipe-card__title">${title}</div>
    <div class="pipe-card__meta"><span class="dotcap dotcap--${color}"></span><span>${meta}</span></div>
  </div>`;
}

/* =============================================================
   ZTP AGENT (site bring-up tracker)
============================================================= */
SCREENS["agent/ztp"] = () => `
<div class="screen is-active" data-route="agent/ztp">
  <div class="row row--between mb-16">
    <div>
      <span class="eyebrow">Agent · 04 / 04</span>
      <h1 class="h2 mt-8">ZTP Agent <em>· Zero-Touch site bring-up</em></h1>
      <span class="muted user-only" style="font-size:12px">Track new sites being brought online. Approve change windows. Cut over to LIVE when KPIs look good.</span>
      <span class="muted mono power-only" style="font-size:11px">v0.2 · Huawei eNB / gNB · 4-stage Day-1 · KPI watch · auto-rollback</span>
    </div>
    <div class="row gap-8">
      <div class="tri power-only">
        <span class="tri__opt tri__opt--off">OFF</span>
        <span class="tri__opt tri__opt--dry is-on">DRY-RUN</span>
        <span class="tri__opt tri__opt--on">AUTONOMOUS</span>
      </div>
      <button class="btn btn--ghost power-only">Synthetic test corpus</button>
      <button class="btn btn--primary">Discover sites</button>
    </div>
  </div>

  <div class="kpi-bar mb-16">
    <div class="kpi-bar__item"><span class="kpi-bar__label">In flight</span><span class="kpi-bar__value">5</span></div>
    <div class="kpi-bar__sep"></div>
    <div class="kpi-bar__item"><span class="kpi-bar__label">LIVE today</span><span class="kpi-bar__value">11</span></div>
    <div class="kpi-bar__sep"></div>
    <div class="kpi-bar__item"><span class="kpi-bar__label">Rollback today</span><span class="kpi-bar__value" style="color:var(--amber)">2</span></div>
    <div class="kpi-bar__sep power-only"></div>
    <div class="kpi-bar__item power-only"><span class="kpi-bar__label">Day-0 P50</span><span class="kpi-bar__value">7m<span style="font-size:14px;color:var(--text-3)"> 12s</span></span></div>
    <div class="kpi-bar__sep power-only"></div>
    <div class="kpi-bar__item power-only"><span class="kpi-bar__label">Day-1 P50</span><span class="kpi-bar__value">26m<span style="font-size:14px;color:var(--text-3)"> 04s</span></span></div>
    <div class="kpi-bar__sep power-only"></div>
    <div class="kpi-bar__item power-only"><span class="kpi-bar__label">PCI auto-resolve</span><span class="kpi-bar__value" style="color:var(--signal)">94.6 %</span></div>
  </div>

  <div class="rule"><span class="rule__index">§ 01</span> Bring-up timeline · enb-LX-0421</div>

  <div class="card" style="padding:24px">
    <div class="row row--between">
      <div>
        <div class="h3">enb-LX-0421 <span class="muted mono" style="font-size:12px;margin-left:8px">site_id 4f7c · Lisbon-East · ETA 04m 12s</span></div>
        <div class="row gap-8 mt-4"><span class="tag tag--violet">PILOT</span><span class="tag tag--cobalt">Day-1 stage 4 / 4</span><span class="tag mono">KPI watch · 12m elapsed</span></div>
      </div>
      <div class="row gap-8">
        <button class="btn btn--sm btn--ghost">Pause</button>
        <button class="btn btn--sm btn--danger">Force rollback</button>
        <button class="btn btn--sm btn--accent">Cut over to LIVE</button>
      </div>
    </div>

    <div class="timeline">
      <div class="tl-step tl-step--done">
        <div class="tl-step__dot"></div>
        <div class="tl-step__label">Discovery</div>
        <div class="tl-step__sub">14:01 · sim_inventory · ✓</div>
      </div>
      <div class="tl-step tl-step--done">
        <div class="tl-step__dot"></div>
        <div class="tl-step__label">Day-0 · bootstrap</div>
        <div class="tl-step__sub">14:09 · NCE-managed · 8m 41s</div>
      </div>
      <div class="tl-step tl-step--done">
        <div class="tl-step__dot"></div>
        <div class="tl-step__label">Day-1 · integration</div>
        <div class="tl-step__sub">14:15 · 4 stages · 26m 04s</div>
      </div>
      <div class="tl-step tl-step--active">
        <div class="tl-step__dot"></div>
        <div class="tl-step__label">KPI watch → LIVE</div>
        <div class="tl-step__sub">12m elapsed · ETA 04m 12s</div>
      </div>
    </div>

    <div class="grid grid-4 mt-24">
      <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">PCI</div><div class="h3" style="font-size:16px;margin-top:4px">211 · auto-resolved</div></div>
      <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">RSRP @ centroid</div><div class="h3" style="font-size:16px;margin-top:4px">–82.4 dBm</div></div>
      <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">Throughput DL</div><div class="h3" style="font-size:16px;margin-top:4px">312 Mbit/s</div></div>
      <div class="card card--quiet" style="padding:14px"><div class="muted mono" style="font-size:10px">DROP RATE</div><div class="h3" style="font-size:16px;margin-top:4px;color:var(--signal)">0.04 %</div></div>
    </div>
  </div>

  <div class="rule"><span class="rule__index">§ 02</span> Site queue</div>

  <div class="card" style="padding:0">
    <table class="tbl">
      <thead><tr><th>Site ID</th><th>Vendor</th><th>Stage</th><th>Started</th><th>ETA</th><th>PCI</th><th>KPI Δ</th><th>Decision</th></tr></thead>
      <tbody>
        <tr><td class="mono">enb-LX-0421</td><td>Huawei</td><td><span class="tag tag--cobalt">KPI watch</span></td><td class="mono">14:09</td><td class="mono">04m 12s</td><td class="mono">211 ✓</td><td class="mono" style="color:var(--emerald)">+1.2 %</td><td><span class="status status--running">auto-cutover</span></td></tr>
        <tr><td class="mono">enb-LX-0424</td><td>Huawei</td><td><span class="tag tag--cobalt">Day-1 stage 3 / 4</span></td><td class="mono">14:15</td><td class="mono">12m 41s</td><td class="mono">214 ✓</td><td class="mono">—</td><td><span class="status status--running">in flight</span></td></tr>
        <tr><td class="mono">gnb-PT-0094</td><td>Huawei</td><td><span class="tag tag--violet">Day-1 stage 1 / 4</span></td><td class="mono">14:18</td><td class="mono">21m 02s</td><td class="mono">—</td><td class="mono">—</td><td><span class="status status--running">in flight</span></td></tr>
        <tr><td class="mono">enb-OPO-0207</td><td>Huawei</td><td><span class="tag tag--amber">Day-0</span></td><td class="mono">14:21</td><td class="mono">06m 12s</td><td class="mono">—</td><td class="mono">—</td><td><span class="status status--running">in flight</span></td></tr>
        <tr><td class="mono">enb-OPO-0208</td><td>Huawei</td><td><span class="tag tag--amber">Discovery</span></td><td class="mono">14:22</td><td class="mono">queued</td><td class="mono">—</td><td class="mono">—</td><td><span class="status status--idle">awaiting window</span></td></tr>
        <tr><td class="mono">enb-AVR-0044</td><td>Huawei</td><td><span class="tag tag--crimson">Rolled back</span></td><td class="mono">13:42</td><td class="mono">—</td><td class="mono">218 ✗</td><td class="mono" style="color:var(--crimson)">−7.4 %</td><td><span class="status status--error">PCI clash · re-plan</span></td></tr>
        <tr><td class="mono">enb-COI-0011</td><td>Huawei</td><td><span class="tag tag--emerald">LIVE</span></td><td class="mono">12:41</td><td class="mono">—</td><td class="mono">209 ✓</td><td class="mono" style="color:var(--emerald)">+0.8 %</td><td><span class="status status--ok">handed off</span></td></tr>
      </tbody>
    </table>
  </div>
</div>
`;

/* =============================================================
   AGENT LIBRARY
============================================================= */
SCREENS.agents = () => `
<div class="screen is-active" data-route="agents">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Agent library</span>
      <h1 class="h2 mt-8">Compose your network <em>operations team</em></h1>
      <p class="lede mt-12">Active agents are wired into the workspace. Pinned agents appear in the sidebar. Draft agents are sandboxed — they read live data but cannot dispatch changes.</p>
    </div>
    <button class="btn btn--primary">+ Build new agent</button>
  </div>

  <div class="row gap-8 mb-16">
    <button class="btn btn--sm">All</button>
    <button class="btn btn--sm btn--ghost">Asset / DB</button>
    <button class="btn btn--sm btn--ghost">Coverage / RF</button>
    <button class="btn btn--sm btn--ghost">CM / Remediation</button>
    <button class="btn btn--sm btn--ghost">Provisioning</button>
    <button class="btn btn--sm btn--ghost">Drafts (3)</button>
    <input class="input" style="margin-left:auto;width:280px" placeholder="Search · 14 agents · 23 templates"/>
  </div>

  <div class="grid grid-3">
    ${[
      {n:"Asset DB",e:"Auditor · Implementor",accent:"emerald",t:"PRODUCTION",sub:"v2.4.1 · 23 threads/day",pin:true},
      {n:"Coverage",e:"RSRP · ASP candidates",accent:"cobalt",t:"PRODUCTION",sub:"v1.6.0 · LTE / NR",pin:true},
      {n:"CM · CoC",e:"Cell-on-Cell remediation",accent:"amber",t:"PILOT",sub:"v0.4 · dry-run",pin:true},
      {n:"ZTP",e:"Site bring-up · Day-0 / Day-1",accent:"violet",t:"PILOT",sub:"v0.2 · 5 in flight",pin:true},
      {n:"Energy",e:"Sleep mode advisor",accent:"emerald",t:"DRAFT",sub:"prototype · sandbox only"},
      {n:"Capacity",e:"Cell load forecasting",accent:"cobalt",t:"DRAFT",sub:"prototype · 30-day forecast"},
      {n:"Audit Sentinel",e:"Daily discrepancy sweep",accent:"amber",t:"PILOT",sub:"cron · 06:00 UTC"},
      {n:"Knowledge",e:"RAG over runbooks · vendor docs",accent:"violet",t:"PRODUCTION",sub:"index · 12 240 docs"},
      {n:"Postmortem",e:"Incident write-up generator",accent:"emerald",t:"DRAFT",sub:"prototype"},
    ].map(a=>`
      <div class="agent-card" data-accent="${a.accent}">
        <div class="agent-card__head">
          <div class="row gap-12">
            <div class="agent-card__icon"><svg viewBox="0 0 20 20" width="20" height="20"><circle cx="10" cy="10" r="3" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" stroke-width="1" stroke-opacity="0.5"/></svg></div>
            <div>
              <div class="agent-card__title">${a.n}</div>
              <div class="agent-card__sub">${a.e}</div>
            </div>
          </div>
          <span class="tag ${a.t==='PRODUCTION'?'tag--emerald':a.t==='PILOT'?'tag--amber':'tag--ghost'}">${a.t}</span>
        </div>
        <div class="muted" style="font-size:12px;margin-top:6px">${a.sub}</div>
        <div class="agent-card__foot">
          <span class="muted mono" style="font-size:11px">${a.pin?'pinned in sidebar':'not pinned'}</span>
          <div class="row gap-6">
            <button class="btn btn--sm btn--ghost">Configure</button>
            ${a.pin?'<button class="btn btn--sm btn--ghost">Open</button>':'<button class="btn btn--sm btn--accent">Pin</button>'}
          </div>
        </div>
      </div>`).join("")}

    <!-- New agent ghost card -->
    <div class="agent-card" style="border:1px dashed var(--line-2);background:transparent;display:flex;align-items:center;justify-content:center;text-align:center;min-height:200px">
      <div>
        <div style="font-size:32px;color:var(--text-3);margin-bottom:8px">+</div>
        <div class="h3">Build a new agent</div>
        <p class="muted" style="font-size:12px;margin-top:6px;max-width:24ch;margin-inline:auto">Start from a template, an OpenAPI tool, or a LangGraph spec.</p>
      </div>
    </div>
  </div>
</div>
`;
SCREENS["agent/coverage"] = () => `
<div class="screen is-active" data-route="agent/coverage">
  <div class="row row--between mb-16">
    <div>
      <span class="eyebrow">Agent · 02 / 04</span>
      <h1 class="h2 mt-8">Coverage <em>Agent</em></h1>
      <span class="muted user-only" style="font-size:12px">Generate RSRP coverage maps for any cells you've selected.</span>
      <span class="muted mono power-only" style="font-size:11px">v1.6.0 · LTE / NR · BIL→PNG (map) · BIL→CSV (report)</span>
    </div>
    <div class="row gap-8">
      <button class="btn btn--ghost">Compare to baseline</button>
      <button class="btn btn--primary">Run coverage</button>
    </div>
  </div>

  <div class="grid" style="grid-template-columns: 320px 1fr 300px; gap:16px; height:calc(100vh - 220px)">
    <!-- chat rail -->
    <aside class="chat-rail" style="height:100%">
      <div class="chat-rail__head"><span class="h4">Conversation</span><span class="tag tag--ghost mono">live</span></div>
      <div class="chat-rail__list" style="padding:18px;display:flex;flex-direction:column;gap:14px">
        <div class="bubble bubble--user"><div class="bubble__body">Run RSRP coverage on the 12 LTE cells I selected in Lisbon-East.</div></div>
        <div class="bubble bubble--assistant">
          <div class="bubble__role"><span class="dotcap dotcap--cobalt"></span>Coverage Agent</div>
          <div class="bubble__body" style="font-size:13px">
            Confirmed. 12 cells selected. Bounding box covers <span class="mono">38.71° N → 38.78° N</span>, <span class="mono">9.10° W → 9.18° W</span>. Will compute RSRP at 50 m resolution. Estimated time <strong>4m 30s</strong>.
          </div>
        </div>
        <div class="bubble bubble--assistant">
          <div class="bubble__role"><span class="dotcap dotcap--cobalt"></span>Coverage Agent</div>
          <div class="bubble__body" style="font-size:13px">
            Map ready · 4 of 12 cells rendered. Streaming progress.
            <div class="callout callout--signal mt-12">
              <strong>Coverage summary ·</strong> 87.4 % above –105 dBm threshold, 4.2 % poor coverage along Av. da Liberdade corridor.
            </div>
          </div>
        </div>
      </div>
      <div class="chat-main__compose" style="border-top:1px solid var(--line)">
        <div class="compose-box">
          <textarea class="compose-input" rows="1" placeholder="Adjust cells, threshold, polygon…"></textarea>
          <div class="compose-row">
            <div class="compose-tools"><button class="compose-tool">@ Polygon</button><button class="compose-tool">@ Threshold</button></div>
            <button class="btn btn--primary btn--sm">Send</button>
          </div>
        </div>
      </div>
    </aside>

    <!-- map -->
    <div class="card" style="padding:0;display:flex;flex-direction:column;overflow:hidden">
      <div class="row row--between" style="padding:12px 16px;border-bottom:1px solid var(--line)">
        <div class="row gap-8">
          <span class="tag tag--cobalt mono">RSRP · LTE</span>
          <span class="muted mono" style="font-size:11px">grid 50 m · 12 cells · job j-7c4</span>
        </div>
        <div class="row gap-6">
          <button class="btn btn--sm btn--ghost">Layers</button>
          <button class="btn btn--sm btn--ghost">Export</button>
          <button class="btn btn--sm btn--ghost">Open in 2D viewer</button>
        </div>
      </div>
      <div class="map-stub">
        <!-- pins -->
        <div class="map-stub__pin" style="top:38%;left:42%"></div>
        <div class="map-stub__pin" style="top:51%;left:55%"></div>
        <div class="map-stub__pin" style="top:62%;left:38%"></div>
        <div class="map-stub__pin" style="top:31%;left:62%"></div>
        <div class="map-stub__pin" style="top:46%;left:71%"></div>

        <!-- centroid label -->
        <div class="map-overlay" style="top:18px;left:18px;max-width:240px">
          <div class="muted mono" style="font-size:10px">SCALE 1:50 000 · EPSG:3763</div>
          <div class="h3 mt-8" style="font-family:var(--f-display)">Lisbon-East</div>
          <div class="muted" style="font-size:11.5px">12 cells · job in progress</div>
          <div class="row gap-12 mt-12">
            <div><div class="muted mono" style="font-size:10px">DONE</div><div class="mono" style="color:var(--signal)">4 / 12</div></div>
            <div><div class="muted mono" style="font-size:10px">ETA</div><div class="mono">2m 51s</div></div>
          </div>
        </div>

        <!-- legend -->
        <div class="map-overlay" style="bottom:18px;left:18px">
          <div class="muted mono" style="font-size:10px;margin-bottom:6px">RSRP · dBm</div>
          <div class="row gap-4">
            <div class="col gap-4">
              <div class="row gap-6"><span style="width:14px;height:10px;background:#00f0c8;border-radius:2px"></span><span class="mono" style="font-size:11px">≥ –75</span></div>
              <div class="row gap-6"><span style="width:14px;height:10px;background:#4dd6a0;border-radius:2px"></span><span class="mono" style="font-size:11px">–85</span></div>
              <div class="row gap-6"><span style="width:14px;height:10px;background:#ffb84d;border-radius:2px"></span><span class="mono" style="font-size:11px">–95</span></div>
              <div class="row gap-6"><span style="width:14px;height:10px;background:#f29333;border-radius:2px"></span><span class="mono" style="font-size:11px">–105</span></div>
              <div class="row gap-6"><span style="width:14px;height:10px;background:#ff6471;border-radius:2px"></span><span class="mono" style="font-size:11px">≤ –115</span></div>
            </div>
          </div>
        </div>

        <!-- progress strip bottom right -->
        <div class="map-overlay" style="bottom:18px;right:18px">
          <div class="muted mono" style="font-size:10px;margin-bottom:6px">JOB · j-7c4</div>
          <div class="mono" style="font-size:11px">Cells: 4 / 12 · 33 %</div>
          <div style="width:200px;height:3px;background:var(--surface-3);border-radius:999px;margin-top:8px;overflow:hidden">
            <div style="width:33%;height:100%;background:linear-gradient(90deg,var(--cobalt),var(--signal));"></div>
          </div>
        </div>

        <div class="map-stub__centroid" style="opacity:0.20;font-size:80px;font-family:var(--f-display);font-weight:300;font-style:italic">L X</div>
      </div>
    </div>

    <!-- layer / cells panel -->
    <aside class="card" style="padding:0;display:flex;flex-direction:column">
      <div style="padding:14px 16px;border-bottom:1px solid var(--line)"><span class="h4">Layers</span></div>
      <div style="padding:12px 16px;border-bottom:1px solid var(--line)">
        ${[
          {n:"RSRP heatmap", on:true, color:"signal"},
          {n:"Cell sites · LTE", on:true, color:"cobalt"},
          {n:"Cell sites · NR", on:false, color:"violet"},
          {n:"User polygon", on:true, color:"amber"},
          {n:"ASP candidates", on:false, color:"emerald"},
          {n:"Roads & landmarks", on:true, color:"emerald"},
        ].map(l=>`
          <div class="row row--between" style="padding:6px 0">
            <span class="row gap-8"><span class="dotcap dotcap--${l.color}"></span><span style="font-size:13px">${l.n}</span></span>
            <span class="toggle ${l.on?'is-on':''}"><span class="toggle__track"><span class="toggle__thumb"></span></span></span>
          </div>`).join("")}
      </div>
      <div style="padding:12px 16px;border-bottom:1px solid var(--line)">
        <span class="h4">Selected cells</span>
        <span class="tag tag--ghost mono" style="margin-left:6px">12</span>
      </div>
      <div style="padding:8px;flex:1;overflow-y:auto">
        ${["1.2.840.0.421","1.2.840.0.422","1.2.840.0.423","1.2.840.0.500","1.2.840.0.501","1.2.840.0.502","1.2.840.0.610","1.2.840.0.611","1.2.840.0.612","1.2.840.0.700","1.2.840.0.701","1.2.840.0.702"].map((c,i)=>`
          <div class="row row--between" style="padding:6px 8px;border-radius:6px">
            <span class="row gap-8"><span class="dotcap ${i<4?'dotcap--signal':''}"></span><span class="mono" style="font-size:11.5px">${c}</span></span>
            <span class="muted mono" style="font-size:10px">${i<4?'done':'queue'}</span>
          </div>`).join("")}
      </div>
    </aside>
  </div>
</div>
`;

/* =============================================================
   SETTINGS — shared shell + nav helper
============================================================= */
function settingsNav(active){
  const items = [
    {g:"Agents", l:[
      {k:"settings/models", t:"Models &amp; routing", s:"per-agent"},
      {k:"settings/flags",  t:"Feature flags",        s:"13"},
      {k:"settings/tools",  t:"Tools &amp; permissions", s:""},
    ]},
    {g:"Workspace", l:[
      {k:"settings/integrations", t:"Integrations",  s:"6"},
      {k:"settings/audit",        t:"Audit log",     s:""},
      {k:"settings/profile",      t:"Profile",       s:""},
    ]},
    {g:"Admin", l:[
      {k:"admin/projects", t:"Projects",     s:"3"},
      {k:"admin/users",    t:"Users &amp; roles", s:"47"},
      {k:"admin/system",   t:"System health", s:""},
    ]},
  ];
  return `
    <aside class="settings-nav">
      ${items.map(g=>`
        <div class="settings-nav__group">${g.g}</div>
        ${g.l.map(i=>`
          <a class="settings-nav__item ${active===i.k?'is-active':''}" href="#${i.k}">
            <span>${i.t}</span>
            ${i.s?`<small>${i.s}</small>`:''}
          </a>
        `).join("")}
      `).join("")}
    </aside>`;
}

/* =============================================================
   SETTINGS · MODELS & ROUTING
============================================================= */
SCREENS["settings/models"] = () => `
<div class="screen is-active" data-route="settings/models">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Settings · Power user</span>
      <h1 class="h2 mt-8">Models <em>&amp; routing</em></h1>
      <p class="lede mt-12">Each agent can pin a model per role (planner, executor, summary). Defaults inherit from workspace. All calls route through OpenRouter unless an integration overrides it.</p>
    </div>
    <div class="row gap-8">
      <button class="btn btn--ghost">Test all routes</button>
      <button class="btn btn--primary">Save changes</button>
    </div>
  </div>

  <div class="settings-shell">
    ${settingsNav("settings/models")}
    <div class="settings-pane">

      <div class="settings-section">
        <div class="settings-section__head">
          <div><div class="h3">Workspace defaults</div><span class="muted mono" style="font-size:11px">applies when an agent does not override</span></div>
          <span class="tag tag--cobalt">OpenRouter</span>
        </div>
        <div class="grid grid-3">
          <div class="field"><span class="field__label">Reasoning model</span><select class="select"><option>qwen3-coder-next</option><option>qwen3.5-flash</option><option>gemini-2.0-flash</option><option>claude-haiku-4-5</option></select><span class="field__hint">Fallback when an agent doesn't set its own.</span></div>
          <div class="field"><span class="field__label">SQL model</span><select class="select"><option>qwen3-32b</option><option>qwen3-coder-next</option></select><span class="field__hint">Used by RAG SQL generator.</span></div>
          <div class="field"><span class="field__label">Summary model</span><select class="select"><option>qwen3.5-flash</option><option>gemini-2.0-flash</option></select><span class="field__hint">Cheap final-answer summariser.</span></div>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section__head"><div class="h3">Per-agent overrides</div><span class="muted mono" style="font-size:11px">click an agent to expand</span></div>

        ${[
          {n:"Asset DB Agent",accent:"emerald",sql:"qwen3-32b",exec:"qwen3-coder-next",sum:"qwen3.5-flash",rec:"4",temp:"0.0"},
          {n:"Coverage Agent",accent:"cobalt",sql:"—",exec:"qwen3-coder-next",sum:"qwen3.5-flash",rec:"6",temp:"0.2"},
          {n:"CM · CoC Agent",accent:"amber",sql:"—",exec:"claude-haiku-4-5",sum:"qwen3.5-flash",rec:"8",temp:"0.0"},
          {n:"ZTP Agent",accent:"violet",sql:"—",exec:"claude-haiku-4-5",sum:"qwen3.5-flash",rec:"6",temp:"0.0"},
        ].map(a=>`
          <div class="card" style="margin-bottom:12px">
            <div class="row row--between">
              <div class="row gap-12">
                <span class="dotcap dotcap--${a.accent}"></span>
                <div>
                  <div class="h3" style="font-size:16px">${a.n}</div>
                  <div class="muted mono" style="font-size:11px">recursion limit ${a.rec} · temp ${a.temp} · top-p 1.0</div>
                </div>
              </div>
              <button class="btn btn--sm btn--ghost">Expand</button>
            </div>
            <div class="grid grid-4 mt-16">
              <div class="card card--quiet" style="padding:12px"><div class="muted mono" style="font-size:10px">SQL</div><div class="mt-4">${a.sql}</div></div>
              <div class="card card--quiet" style="padding:12px"><div class="muted mono" style="font-size:10px">EXECUTOR</div><div class="mt-4">${a.exec}</div></div>
              <div class="card card--quiet" style="padding:12px"><div class="muted mono" style="font-size:10px">SUMMARY</div><div class="mt-4">${a.sum}</div></div>
              <div class="card card--quiet" style="padding:12px"><div class="muted mono" style="font-size:10px">SPEND (MTD)</div><div class="mt-4 mono" style="color:var(--signal)">$${(Math.random()*60+18).toFixed(2)}</div></div>
            </div>
          </div>
        `).join("")}
      </div>

      <div class="settings-section">
        <div class="settings-section__head"><div class="h3">Routing &amp; fallbacks</div></div>
        <div class="card">
          <div class="row row--between mb-16"><div><strong>Primary route</strong> · OpenRouter</div><span class="status status--ok">healthy · 92ms</span></div>
          <div class="row row--between mb-16"><div><strong>Fallback A</strong> · Anthropic Direct</div><span class="status status--ok">healthy · 184ms</span></div>
          <div class="row row--between mb-16"><div><strong>Fallback B</strong> · Local vLLM (qwen3-32b)</div><span class="status status--idle">cold · pre-warm on demand</span></div>
          <div class="callout">If primary returns 5xx for &gt; 3 consecutive calls, traffic auto-fails over to A. Local fallback only used during external incident.</div>
        </div>
      </div>
    </div>
  </div>
</div>
`;

/* =============================================================
   SETTINGS · FEATURE FLAGS
============================================================= */
SCREENS["settings/flags"] = () => `
<div class="screen is-active" data-route="settings/flags">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Settings · Power user</span>
      <h1 class="h2 mt-8">Feature flags <em>· autonomy gates</em></h1>
      <p class="lede mt-12">Every autonomous behaviour can be flipped between OFF, DRY-RUN, and AUTONOMOUS. Changes are live and logged in the audit trail.</p>
    </div>
    <div class="row gap-8">
      <button class="btn btn--danger">Kill switch · all autonomous</button>
      <button class="btn btn--primary">Save changes</button>
    </div>
  </div>

  <div class="settings-shell">
    ${settingsNav("settings/flags")}
    <div class="settings-pane">
      <div class="callout callout--amber mb-16"><strong>2 flags</strong> are currently OFF and <strong>9 flags</strong> are in DRY-RUN. Only <strong>2</strong> are AUTONOMOUS — pinned cells discovery and asset DB read-only RAG.</div>

      ${[
        {g:"CM · Cell-on-Cell", flags: [
          {k:"CM_AUTONOMOUS_MODE", d:"Master autonomy gate. When OFF, agent runs but never dispatches.", state:"dry"},
          {k:"CM_AUTO_MATERIALIZE", d:"Insert candidate row in COC_CANDIDATE_1 without operator confirm.", state:"dry"},
          {k:"CM_AUTO_DISPATCH", d:"Send Huawei MO XML to NCE Gatekeeper without operator confirm.", state:"off"},
          {k:"CM_AUTO_ROLLBACK", d:"On KPI regression &gt; threshold, dispatch revert to NCE.", state:"dry"},
          {k:"CM_SHADOW_MODE", d:"Run all stages, write decisions, but block execution path.", state:"on"},
        ]},
        {g:"ZTP · Site bring-up", flags: [
          {k:"ZTP_AUTONOMOUS_MODE", d:"Master gate for ZTP execution.", state:"dry"},
          {k:"ZTP_AUTO_PCI_RESOLVE", d:"Auto-pick conflict-free PCI from candidate set.", state:"dry"},
          {k:"ZTP_AUTO_KPI_CUTOVER", d:"Promote site to LIVE without operator click.", state:"off"},
          {k:"ZTP_AUTO_ROLLBACK", d:"Revert Day-1 changes on KPI regression.", state:"dry"},
        ]},
        {g:"Asset DB", flags: [
          {k:"DBA_RAG_AUTONOMOUS", d:"Allow read-only SQL without per-call confirm. Always safe.", state:"on"},
          {k:"DBA_AUTO_FIX", d:"EDS Fixer can apply staged fixes without operator click.", state:"off"},
          {k:"DBA_COLUMN_PREFETCH", d:"Bulletproof column search runs before every LLM attempt.", state:"on"},
          {k:"DBA_LOOP_DETECTOR", d:"Per-tool count + consecutive limit hard-cap.", state:"on"},
        ]},
      ].map(g=>`
        <div class="settings-section">
          <div class="settings-section__head"><div class="h3">${g.g}</div><span class="muted mono" style="font-size:11px">${g.flags.length} flags</span></div>
          <div class="card" style="padding:0">
            <table class="tbl">
              <thead><tr><th>Flag</th><th style="width:40%">Description</th><th>State</th><th>Last changed</th><th></th></tr></thead>
              <tbody>
                ${g.flags.map(f=>`
                  <tr>
                    <td class="mono">${f.k}</td>
                    <td>${f.d}</td>
                    <td>
                      <div class="tri">
                        <span class="tri__opt tri__opt--off ${f.state==='off'?'is-on':''}">OFF</span>
                        <span class="tri__opt tri__opt--dry ${f.state==='dry'?'is-on':''}">DRY-RUN</span>
                        <span class="tri__opt tri__opt--on  ${f.state==='on'?'is-on':''}">ON</span>
                      </div>
                    </td>
                    <td class="mono">${["2 days · biman","6 days · chandan","17 days · biman","22 days · chandan"][Math.floor(Math.random()*4)]}</td>
                    <td><button class="btn btn--sm btn--ghost">History</button></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `).join("")}
    </div>
  </div>
</div>
`;

/* =============================================================
   SETTINGS · INTEGRATIONS
============================================================= */
SCREENS["settings/integrations"] = () => `
<div class="screen is-active" data-route="settings/integrations">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Settings · Power user</span>
      <h1 class="h2 mt-8">Integrations</h1>
      <p class="lede mt-12">Live connections to network and platform systems. Simulators are clearly marked — they will be swapped to real endpoints during production cutover.</p>
    </div>
    <button class="btn btn--primary">+ Add integration</button>
  </div>

  <div class="settings-shell">
    ${settingsNav("settings/integrations")}
    <div class="settings-pane">
      <div class="grid grid-2">
        ${[
          {n:"PostgreSQL · cm_platform",cat:"Datastore",status:"ok",detail:"pool 8/40 · 4ms · csv_user / app_rls_user",mono:"postgres://postgres:5432/cm_platform"},
          {n:"Redis",cat:"Queue · streams",status:"ok",detail:"0.6ms · 312 messages/min",mono:"redis://redis:6379"},
          {n:"Keycloak",cat:"Identity",status:"ok",detail:"realm aan-realm · 47 sessions · CONFIG_MANAGEMENT role",mono:"https://auth.grgd-scm-vm01.../auth/realms/aan-realm"},
          {n:"Phoenix · tracing",cat:"Observability",status:"ok",detail:"312 spans/min · OTel collector",mono:"http://phoenix:6006"},
          {n:"OpenRouter",cat:"LLM gateway",status:"ok",detail:"primary · 92ms p50 · $184.22 MTD",mono:"https://openrouter.ai/api/v1"},
          {n:"Huawei iMaster NCE",cat:"Vendor NBI",status:"sim",detail:"sim_nce · :9443 · in-memory SimENB · 50 site capacity",mono:"https://sim_nce:9443/scm/gatekeeper/v1"},
          {n:"Oracle SCMPRD01",cat:"NiFi legacy",status:"sim",detail:"sim_oracle · SQLite + 4 view mocks · COC_CANDIDATE_1_INSERT",mono:"sqlite://sim_oracle.db"},
          {n:"NetAct (planned)",cat:"OSS",status:"pending",detail:"awaiting POC sign-off · used by ZTP planner",mono:"https://netact.../api"},
        ].map(i=>{
          const dotColor = i.status==="ok"?"emerald":i.status==="sim"?"amber":"text-3";
          const tag = i.status==="ok"?'<span class="tag tag--emerald">CONNECTED</span>'
                    : i.status==="sim"?'<span class="tag tag--amber">SIMULATOR</span>'
                    :'<span class="tag tag--ghost">PENDING</span>';
          return `
          <div class="card">
            <div class="row row--between">
              <div>
                <div class="muted mono" style="font-size:10px">${i.cat}</div>
                <div class="h3" style="margin-top:4px">${i.n}</div>
              </div>
              ${tag}
            </div>
            <div class="muted" style="font-size:13px;margin-top:10px">${i.detail}</div>
            <div class="mono" style="font-size:11px;color:var(--text-3);margin-top:8px;padding:8px 10px;background:var(--ink);border:1px solid var(--line);border-radius:8px;overflow-x:auto;white-space:nowrap">${i.mono}</div>
            <div class="agent-card__foot">
              <span class="status status--${i.status==='ok'?'ok':i.status==='sim'?'pending':'idle'}">${i.status==='ok'?'live':i.status==='sim'?'simulator':'pending'}</span>
              <div class="row gap-6">
                <button class="btn btn--sm btn--ghost">Test</button>
                <button class="btn btn--sm btn--ghost">Configure</button>
              </div>
            </div>
          </div>`;
        }).join("")}
      </div>

      <div class="rule mt-24"><span class="rule__index">§ 02</span> Production cutover path</div>
      <div class="callout callout--signal">
        <strong>Sim → real swap:</strong> setting <span class="mono">CM_USE_SIMULATORS=false</span> + <span class="mono">NCE_URL</span> swaps simulators to live NCE without code changes. Shadow mode (<span class="mono">CM_SHADOW_MODE=on</span>) recommended for 2 weeks before flipping autonomy.
      </div>
    </div>
  </div>
</div>
`;

/* =============================================================
   SETTINGS · AUDIT LOG
============================================================= */
SCREENS["settings/audit"] = () => `
<div class="screen is-active" data-route="settings/audit">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Settings · Power user</span>
      <h1 class="h2 mt-8">Audit log</h1>
      <p class="lede mt-12">Every flag flip, model change, role grant, and dispatch decision is appended here. Append-only. Exportable to CSV / Phoenix.</p>
    </div>
    <div class="row gap-8">
      <input class="input" placeholder="Filter · actor, action, target…" style="width:280px"/>
      <button class="btn btn--ghost">Export CSV</button>
    </div>
  </div>

  <div class="settings-shell">
    ${settingsNav("settings/audit")}
    <div class="settings-pane">
      <div class="card" style="padding:0">
        <table class="tbl">
          <thead><tr><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Target</th><th>Before → After</th><th>Source</th></tr></thead>
          <tbody>
            <tr><td class="mono">2026-04-27 14:11:04</td><td>cm_agent</td><td>flag.read</td><td class="mono">CM_AUTONOMOUS_MODE</td><td class="mono">— → DRY-RUN</td><td><span class="tag mono">agent</span></td></tr>
            <tr><td class="mono">2026-04-27 13:42:11</td><td>cm_orch</td><td>autorollback</td><td class="mono">candidate-1748</td><td class="mono">DISPATCHED → ROLLED_BACK</td><td><span class="tag mono">agent</span></td></tr>
            <tr><td class="mono">2026-04-27 09:14:00</td><td>biman@teoco.com</td><td>flag.update</td><td class="mono">CM_AUTONOMOUS_MODE</td><td class="mono">OFF → DRY-RUN</td><td><span class="tag tag--cobalt mono">human</span></td></tr>
            <tr><td class="mono">2026-04-27 08:02:33</td><td>chandan@teoco.com</td><td>model.update</td><td class="mono">cm_agent.executor</td><td class="mono">qwen3-32b → claude-haiku-4-5</td><td><span class="tag tag--cobalt mono">human</span></td></tr>
            <tr><td class="mono">2026-04-26 18:22:11</td><td>chandan@teoco.com</td><td>integration.add</td><td class="mono">openrouter</td><td class="mono">— → connected</td><td><span class="tag tag--cobalt mono">human</span></td></tr>
            <tr><td class="mono">2026-04-26 11:41:09</td><td>biman@teoco.com</td><td>role.grant</td><td class="mono">rohit@teoco.com</td><td class="mono">user → power_user</td><td><span class="tag tag--cobalt mono">human</span></td></tr>
            <tr><td class="mono">2026-04-25 14:33:47</td><td>ztp_agent</td><td>autonomy.gate</td><td class="mono">enb-AVR-0044</td><td class="mono">DAY1 → ROLLED_BACK</td><td><span class="tag mono">agent</span></td></tr>
            <tr><td class="mono">2026-04-22 09:14:21</td><td>biman@teoco.com</td><td>flag.update</td><td class="mono">CM_SHADOW_MODE</td><td class="mono">DRY-RUN → ON</td><td><span class="tag tag--cobalt mono">human</span></td></tr>
            <tr><td class="mono">2026-04-22 08:01:00</td><td>chandan@teoco.com</td><td>session.delete</td><td class="mono">acss · 8af1-23bc-…</td><td class="mono">existed → removed</td><td><span class="tag tag--cobalt mono">human</span></td></tr>
            <tr><td class="mono">2026-04-20 16:18:12</td><td>chandan@teoco.com</td><td>workspace.create</td><td class="mono">NOS Portugal</td><td class="mono">— → active</td><td><span class="tag tag--cobalt mono">human</span></td></tr>
          </tbody>
        </table>
      </div>
      <div class="row row--between mt-16"><span class="muted mono" style="font-size:11px">Showing 10 of 4 218 entries</span><div class="row gap-8"><button class="btn btn--sm btn--ghost">‹ Prev</button><button class="btn btn--sm btn--ghost">Next ›</button></div></div>
    </div>
  </div>
</div>
`;

/* =============================================================
   SETTINGS · TOOLS & PERMISSIONS
============================================================= */
SCREENS["settings/tools"] = () => `
<div class="screen is-active" data-route="settings/tools">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Settings · Power user</span>
      <h1 class="h2 mt-8">Tools <em>&amp; permissions</em></h1>
      <p class="lede mt-12">Every tool an agent can call is declared here. Toggle at the workspace level; per-agent overrides live on the agent's configure pane.</p>
    </div>
  </div>
  <div class="settings-shell">
    ${settingsNav("settings/tools")}
    <div class="settings-pane">
      ${[
        {g:"Asset DB", tools:[
          {n:"asset_db_rag_tool", d:"Read-only SQL with smart column hints + retry", scope:"RLS-scoped read", risk:"low", on:true},
          {n:"audit_engine_tool", d:"Cross-table consistency audit", scope:"read", risk:"low", on:true},
          {n:"discrepancy_engine_tool", d:"Surface deltas vs planned configuration", scope:"read", risk:"low", on:true},
          {n:"run_eds_fixer_tool", d:"Apply EDS fix to source-of-truth row", scope:"write · staging", risk:"med", on:true},
          {n:"update_eds_tool", d:"Push fix to EDS bus", scope:"write · prod", risk:"high", on:false},
        ]},
        {g:"Coverage", tools:[
          {n:"get_cell_iids", d:"Resolve cells from polygon / region", scope:"RLS-scoped read", risk:"low", on:true},
          {n:"run_coverage_job", d:"BIL → PNG / CSV via coverage API", scope:"compute", risk:"low", on:true},
        ]},
        {g:"CM · Cell-on-Cell", tools:[
          {n:"materialize_candidate", d:"Insert candidate row · COC_CANDIDATE_1", scope:"write · oracle", risk:"med", on:true},
          {n:"build_huawei_template", d:"Render MO XML for NCE", scope:"compute", risk:"low", on:true},
          {n:"dispatch_to_orch", d:"Send to cm_orch worker pool", scope:"queue", risk:"med", on:true},
          {n:"rollback_change", d:"Revert dispatched MO XML on NCE", scope:"write · vendor", risk:"high", on:true},
        ]},
        {g:"ZTP", tools:[
          {n:"discover_site", d:"Pull from sim_inventory / NetAct", scope:"read", risk:"low", on:true},
          {n:"day0_bootstrap", d:"Onboard eNB / gNB to NCE", scope:"write · vendor", risk:"high", on:true},
          {n:"day1_integrate", d:"Push planning + neighbour list", scope:"write · vendor", risk:"high", on:true},
          {n:"kpi_watch", d:"Subscribe to OSS counters · 30 min window", scope:"read · oss", risk:"low", on:true},
        ]},
      ].map(g=>`
        <div class="settings-section">
          <div class="settings-section__head"><div class="h3">${g.g}</div></div>
          <div class="card" style="padding:0">
            <table class="tbl">
              <thead><tr><th>Tool</th><th style="width:40%">Description</th><th>Scope</th><th>Risk</th><th>Workspace</th></tr></thead>
              <tbody>
                ${g.tools.map(t=>`
                  <tr>
                    <td class="mono">${t.n}</td>
                    <td>${t.d}</td>
                    <td><span class="tag mono">${t.scope}</span></td>
                    <td>${t.risk==="high"?'<span class="tag tag--crimson">HIGH</span>':t.risk==="med"?'<span class="tag tag--amber">MED</span>':'<span class="tag tag--emerald">LOW</span>'}</td>
                    <td><span class="toggle ${t.on?'is-on':''}"><span class="toggle__track"><span class="toggle__thumb"></span></span></span></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `).join("")}
    </div>
  </div>
</div>
`;

/* =============================================================
   SETTINGS · PROFILE
============================================================= */
SCREENS["settings/profile"] = () => `
<div class="screen is-active" data-route="settings/profile">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Settings</span>
      <h1 class="h2 mt-8">Profile <em>&amp; preferences</em></h1>
    </div>
  </div>
  <div class="settings-shell">
    ${settingsNav("settings/profile")}
    <div class="settings-pane">
      <div class="card mb-16">
        <div class="row gap-16">
          <div class="rail__user-avatar" style="width:64px;height:64px;border-radius:14px;font-size:24px">CS</div>
          <div class="flex-1">
            <div class="h3">Chandan Singh</div>
            <div class="muted mono" style="font-size:12px">chandan.singh@teoco.com · Power user · CONFIG_MANAGEMENT</div>
            <div class="row gap-6 mt-8"><span class="tag tag--cobalt">DB Agent owner</span><span class="tag tag--cobalt">CM Agent reviewer</span><span class="tag mono">SSO via Keycloak</span></div>
          </div>
        </div>
      </div>
      <div class="grid grid-2">
        <div class="card">
          <div class="h3 mb-16">Display</div>
          <div class="field"><span class="field__label">Theme</span><div class="row gap-8"><button class="btn btn--sm">Operator (dark)</button><button class="btn btn--sm btn--ghost">Daylight (light)</button><button class="btn btn--sm btn--ghost">System</button></div></div>
          <div class="field"><span class="field__label">Density</span><div class="row gap-8"><button class="btn btn--sm btn--ghost">Comfortable</button><button class="btn btn--sm">Compact</button><button class="btn btn--sm btn--ghost">Dense</button></div></div>
          <div class="field"><span class="field__label">Show wireframe banner</span><span class="toggle is-on"><span class="toggle__track"><span class="toggle__thumb"></span></span></span></div>
        </div>
        <div class="card">
          <div class="h3 mb-16">Notifications</div>
          ${["CoC pair pending review","ZTP rollback occurred","DB Agent: 200+ messages in thread","Keycloak token refresh failed","Daily summary email · 18:00 UTC"].map(n=>`
            <div class="row row--between" style="padding:8px 0;border-bottom:1px solid var(--line)">
              <span>${n}</span>
              <span class="toggle ${Math.random()>0.3?'is-on':''}"><span class="toggle__track"><span class="toggle__thumb"></span></span></span>
            </div>`).join("")}
        </div>
      </div>
    </div>
  </div>
</div>
`;

/* =============================================================
   ADMIN · PROJECTS
============================================================= */
SCREENS["admin/projects"] = () => `
<div class="screen is-active" data-route="admin/projects">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Admin · Power user</span>
      <h1 class="h2 mt-8">Projects <em>&amp; workspaces</em></h1>
      <p class="lede mt-12">Each project is an isolated namespace: its own RLS scope, cell catalogue, agent state, and ASP sessions.</p>
    </div>
    <button class="btn btn--primary">+ New project</button>
  </div>
  <div class="settings-shell">
    ${settingsNav("admin/projects")}
    <div class="settings-pane">
      <div class="card" style="padding:0;margin-bottom:16px">
        <table class="tbl">
          <thead><tr><th>Project</th><th>Cells</th><th>Sites</th><th>Owners</th><th>RLS</th><th>Imported</th><th>Status</th><th></th></tr></thead>
          <tbody>
            <tr><td><strong>NOS Portugal</strong><br/><span class="muted mono" style="font-size:10px">nos_portugal · pinned</span></td><td class="num">4 281</td><td class="num">1 207</td><td>Chandan, Biman, Rohit</td><td><span class="tag tag--emerald">ON</span></td><td class="mono">2026-04-07</td><td><span class="status status--ok">live</span></td><td><button class="btn btn--sm btn--ghost">Configure</button></td></tr>
            <tr><td><strong>BT UK · trial</strong><br/><span class="muted mono" style="font-size:10px">bt_uk_trial</span></td><td class="num">988</td><td class="num">241</td><td>Biman</td><td><span class="tag tag--emerald">ON</span></td><td class="mono">2026-03-22</td><td><span class="status status--ok">live</span></td><td><button class="btn btn--sm btn--ghost">Configure</button></td></tr>
            <tr><td><strong>Demo · sandbox</strong><br/><span class="muted mono" style="font-size:10px">demo_sandbox</span></td><td class="num">120</td><td class="num">35</td><td>—</td><td><span class="tag tag--ghost">OFF</span></td><td class="mono">2026-04-20</td><td><span class="status status--idle">paused</span></td><td><button class="btn btn--sm btn--ghost">Configure</button></td></tr>
          </tbody>
        </table>
      </div>

      <div class="rule"><span class="rule__index">§ 02</span> Project · NOS Portugal</div>

      <div class="grid grid-2">
        <div class="card">
          <div class="h3 mb-16">Schema &amp; ingestion</div>
          <div class="row row--between" style="padding:8px 0;border-bottom:1px solid var(--line)"><span>cell_lte</span><span class="mono">3 890 rows · indexed</span></div>
          <div class="row row--between" style="padding:8px 0;border-bottom:1px solid var(--line)"><span>cell_nr</span><span class="mono">391 rows · indexed</span></div>
          <div class="row row--between" style="padding:8px 0;border-bottom:1px solid var(--line)"><span>cell_physical_antenna</span><span class="mono">8 562 rows · indexed</span></div>
          <div class="row row--between" style="padding:8px 0;border-bottom:1px solid var(--line)"><span>antennadevice</span><span class="mono">1 207 rows · indexed</span></div>
          <div class="row row--between" style="padding:8px 0"><span>Last import</span><span class="mono">2026-04-22 04:00 UTC · 41s</span></div>
        </div>
        <div class="card">
          <div class="h3 mb-16">Encryption &amp; hashing</div>
          <div class="field"><span class="field__label">ENCRYPTION_ENABLED</span><span class="toggle is-on"><span class="toggle__track"><span class="toggle__thumb"></span></span></span><span class="field__hint">Row-level encryption on sensitive columns.</span></div>
          <div class="field"><span class="field__label">IID_HASHING_ENABLED</span><span class="toggle is-on"><span class="toggle__track"><span class="toggle__thumb"></span></span></span><span class="field__hint">BLAKE2b hash of cell / site IDs at pipeline level. Reverse-mapped at runtime.</span></div>
          <div class="callout callout--signal">Verified via Phoenix · zero raw IIDs visible to LLMs.</div>
        </div>
      </div>
    </div>
  </div>
</div>
`;

/* =============================================================
   ADMIN · USERS
============================================================= */
SCREENS["admin/users"] = () => `
<div class="screen is-active" data-route="admin/users">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Admin · Power user</span>
      <h1 class="h2 mt-8">Users <em>&amp; roles</em></h1>
      <p class="lede mt-12">Identity comes from Keycloak. Roles map to realm roles. RLS scope is computed per-user from <span class="mono">user_project_config.cell_iids</span>.</p>
    </div>
    <div class="row gap-8">
      <input class="input" placeholder="Search 47 users…" style="width:240px"/>
      <button class="btn btn--primary">+ Invite user</button>
    </div>
  </div>
  <div class="settings-shell">
    ${settingsNav("admin/users")}
    <div class="settings-pane">
      <div class="card" style="padding:0">
        <table class="tbl">
          <thead><tr><th>User</th><th>Realm role</th><th>Workspaces</th><th>RLS scope</th><th>Last seen</th><th>MFA</th><th></th></tr></thead>
          <tbody>
            ${[
              ["Chandan Singh","chandan.singh@teoco.com","CONFIG_MANAGEMENT · power_user","NOS Portugal","3 128 cells","just now",true],
              ["Biman Banerjee","biman@teoco.com","CONFIG_MANAGEMENT · power_user","NOS · BT UK","all (admin)","2 min",true],
              ["Rohit Kumar","rohit@teoco.com","power_user","NOS Portugal","1 247 cells","17 min",true],
              ["Ana Costa","ana.costa@teoco.com","user","NOS Portugal","412 cells","yesterday",true],
              ["Demo Account","demo@teoco.com","viewer","Demo sandbox","120 cells","3 days",false],
              ["Service · cm_agent","cm_agent@svc","service","NOS · BT UK","read · audit","always",false],
              ["Service · ztp_agent","ztp_agent@svc","service","NOS Portugal","read · audit","always",false],
            ].map(u=>`
              <tr>
                <td><strong>${u[0]}</strong><br/><span class="muted mono" style="font-size:10px">${u[1]}</span></td>
                <td>${u[2].split(" · ").map(r=>`<span class="tag mono" style="margin-right:4px">${r}</span>`).join("")}</td>
                <td>${u[3]}</td>
                <td class="mono">${u[4]}</td>
                <td class="mono">${u[5]}</td>
                <td>${u[6]?'<span class="tag tag--emerald">ON</span>':'<span class="tag tag--ghost">—</span>'}</td>
                <td><button class="btn btn--sm btn--ghost">Edit</button></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>

      <div class="rule mt-24"><span class="rule__index">§ 02</span> Roles &amp; capabilities</div>

      <div class="grid grid-3">
        ${[
          {n:"viewer",c:["Read agent threads","View dashboards","No write access"]},
          {n:"user",c:["Run agents in DRY-RUN","Stage fixes for review","Cannot toggle flags"]},
          {n:"power_user",c:["Approve dispatches","Toggle DRY-RUN ↔ ON","Configure tools per agent"]},
          {n:"CONFIG_MANAGEMENT",c:["Project setup","Schema imports","RLS scope edits"]},
          {n:"admin",c:["User invites","Role grants","Workspace create / archive"]},
          {n:"service (svc)",c:["Used by agents","Cannot log in interactively","Read · audit only"]},
        ].map(r=>`
          <div class="card">
            <div class="h3" style="font-family:var(--f-mono);font-size:14px;letter-spacing:0.04em;text-transform:uppercase;color:var(--cobalt)">${r.n}</div>
            <div class="col gap-4 mt-12">
              ${r.c.map(x=>`<div class="row gap-8"><span class="dotcap dotcap--cobalt"></span><span style="font-size:13px">${x}</span></div>`).join("")}
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  </div>
</div>
`;

/* =============================================================
   ADMIN · SYSTEM HEALTH
============================================================= */
SCREENS["admin/system"] = () => `
<div class="screen is-active" data-route="admin/system">
  <div class="row row--between mb-24">
    <div>
      <span class="eyebrow">Admin · Power user</span>
      <h1 class="h2 mt-8">System health</h1>
      <p class="lede mt-12">Service map for the Operator Console stack. All services live on <span class="mono">grgd-scm-vm01.ap.teo.earth</span>.</p>
    </div>
    <div class="row gap-8"><button class="btn btn--ghost">Open Phoenix</button><button class="btn btn--primary">Run health checks</button></div>
  </div>
  <div class="settings-shell">
    ${settingsNav("admin/system")}
    <div class="settings-pane">
      <div class="grid grid-3 mb-16">
        <div class="stat"><span class="stat__label">Avg latency · all agents</span><span class="stat__value">1.8<span style="font-size:18px;color:var(--text-3)"> s</span></span><svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none"><path d="M0,14 L20,11 L40,17 L60,9 L80,12 L100,7"/></svg></div>
        <div class="stat"><span class="stat__label">Tool calls (last hour)</span><span class="stat__value">874</span><svg class="spark spark--signal" viewBox="0 0 100 28" preserveAspectRatio="none"><path d="M0,18 L15,15 L30,17 L45,10 L60,12 L75,8 L90,11 L100,6"/></svg></div>
        <div class="stat"><span class="stat__label">Error rate (24h)</span><span class="stat__value" style="color:var(--emerald)">0.31<span style="font-size:18px;color:var(--text-3)"> %</span></span><svg class="spark spark--emerald" viewBox="0 0 100 28" preserveAspectRatio="none"><path d="M0,24 L25,22 L50,21 L75,23 L100,22"/></svg></div>
      </div>

      <div class="card mb-16" style="padding:0">
        <div style="padding:14px 18px;border-bottom:1px solid var(--line)" class="row row--between">
          <div class="h3">Service map</div>
          <span class="muted mono" style="font-size:11px">docker-compose · 14 services</span>
        </div>
        <div style="padding:18px">
          <div class="grid" style="grid-template-columns:repeat(7,1fr);gap:10px">
            ${[
              ["frontend","ok"],["agent_server (LangGraph)","ok"],["asp_server","ok"],["agent-worker","ok"],
              ["cm_agent","ok"],["cm_orch","ok"],["ztp_agent","ok"],
              ["sim_oracle","sim"],["sim_nce","sim"],["sim_inventory","sim"],
              ["postgres","ok"],["redis","ok"],["phoenix","ok"],["keycloak","ok"],
            ].map(s=>`
              <div class="card card--quiet" style="padding:12px;text-align:center">
                <div class="dotcap ${s[1]==='ok'?'dotcap--emerald':'dotcap--amber'}" style="margin:0 auto 6px"></div>
                <div class="mono" style="font-size:11px;color:var(--text)">${s[0]}</div>
                <div class="muted mono" style="font-size:9.5px;margin-top:2px">${s[1]==='ok'?'live':'simulator'}</div>
              </div>
            `).join("")}
          </div>
        </div>
      </div>

      <div class="grid grid-2">
        <div class="card">
          <div class="h3 mb-16">Resource use</div>
          ${[["CPU · user space",42,"emerald"],["CPU · kernel",8,"emerald"],["Memory · RSS",64,"emerald"],["Postgres connections","8 / 40","cobalt"],["Redis memory",18,"emerald"]].map(r=>{
            const isPct = typeof r[1]==='number';
            return `
            <div style="padding:8px 0;border-bottom:1px solid var(--line)">
              <div class="row row--between"><span>${r[0]}</span><span class="mono" style="color:var(--${r[2]})">${isPct?r[1]+' %':r[1]}</span></div>
              ${isPct?`<div style="height:3px;background:var(--surface-3);border-radius:999px;margin-top:6px;overflow:hidden"><div style="width:${r[1]}%;height:100%;background:var(--${r[2]})"></div></div>`:''}
            </div>`;
          }).join("")}
        </div>
        <div class="card">
          <div class="h3 mb-16">Recent incidents</div>
          ${[
            ["2026-04-22 09:14","CM Agent flag flipped to DRY-RUN","biman","resolved"],
            ["2026-04-20 11:03","useStream SDK O(n²) freeze · 200+ msg","frontend","known · SDK upstream"],
            ["2026-04-07 06:42","Coverage Agent get_cell_iids regression","rohit","fix · b3a91f"],
          ].map(i=>`
            <div style="padding:10px 0;border-bottom:1px solid var(--line)">
              <div class="row row--between"><strong style="font-size:13px">${i[1]}</strong><span class="muted mono" style="font-size:10.5px">${i[0]}</span></div>
              <div class="muted mono" style="font-size:11px;margin-top:2px">${i[2]} · <span style="color:var(--emerald)">${i[3]}</span></div>
            </div>
          `).join("")}
        </div>
      </div>
    </div>
  </div>
</div>
`;

/* =============================================================
   FALLBACKS · routes that link from rail but reuse another screen
============================================================= */
SCREENS.threads   = SCREENS["agent/asset-db"];
SCREENS.sessions  = SCREENS["agent/coverage"];
SCREENS.reports   = SCREENS.home;
