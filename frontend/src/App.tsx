import { createContext, useContext, useEffect, useRef, useState, ReactNode } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, BarChart, Bar, CartesianGrid, ResponsiveContainer } from "recharts";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const API: string = (import.meta as any).env.VITE_API_BASE || (location.hostname === "localhost" ? "http://127.0.0.1:8000" : "https://water-leak-ai-j7h6.onrender.com");
const j = async (u: string, m = "GET") => (await fetch(API + u, { method: m })).json();
const Ctx = createContext<any>(null);
const useR = () => useContext(Ctx);
const SCEN = ["leak", "normal", "bad_sensor", "flow_only", "pressure_only"];

const Card = ({ t, children }: { t?: string; children: ReactNode }) => (<div className="bg-white rounded-xl border p-4 mb-4">{t && <h3 className="font-semibold mb-2">{t}</h3>}{children}</div>);
const Table = ({ head, rows }: { head: string[]; rows: any[][] }) => (<div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr>{head.map(h => <th key={h} className="text-left border-b p-1">{h}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, k) => <td key={k} className="border-b p-1 align-top">{c}</td>)}</tr>)}</tbody></table></div>);
const Btn = ({ onClick, children }: any) => <button onClick={onClick} className="px-3 py-1 mr-2 mt-1 rounded bg-slate-800 text-white text-sm hover:bg-slate-600">{children}</button>;
const Flow = ({ s, title }: any) => { const d = s.t.map((t: string, i: number) => ({ t, actual: s.actual[i], forecast: s.forecast[i] })); return (<Card t={title}><ResponsiveContainer width="100%" height={230}><LineChart data={d}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" /><YAxis domain={["auto", "auto"]} /><Tooltip /><Legend /><Line dataKey="actual" stroke="#2563eb" /><Line dataKey="forecast" stroke="#e11d48" /></LineChart></ResponsiveContainer></Card>); };
const Bars = ({ data, keys, title }: any) => (<Card t={title}><ResponsiveContainer width="100%" height={230}><BarChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="zone" /><YAxis /><Tooltip /><Legend />{keys.map((k: string, i: number) => <Bar key={k} dataKey={k} fill={["#2563eb", "#e11d48", "#16a34a"][i]} />)}</BarChart></ResponsiveContainer></Card>);
const zones = (r: any) => Object.entries(r.anomalies) as [string, any][];

async function act(u: string, reload: () => void) { const x = await j(u, "POST"); alert(JSON.stringify(x, null, 1)); reload(); }

function Dashboard() {
  const { r } = useR(); const [st, setSt] = useState<any>({ teams: {} });
  useEffect(() => { j("/api/state").then(setSt); }, [r]);
  if (!r) return null; const z = zones(r).map(e => e[1]);
  const k: [string, any][] = [["Monitored zones", z.length], ["Current supply (m³/h)", z.reduce((s, a) => s + a.inlet_mean, 0).toFixed(0)], ["Forecast demand (m³/h)", z.reduce((s, a) => s + a.forecast_mean, 0).toFixed(0)],
    ["Active leak hypotheses", r.leaks.length], ["Repairs recorded", r.leaks.filter((l: any) => l.workflow.startsWith("REPAIR")).length], ["Est. water loss (m³)", r.leaks.reduce((s: number, l: any) => s + l.est_loss_m3, 0).toFixed(0)],
    ["Low-pressure zones", z.filter(a => a.pressure_anomaly).length], ["Sensor failures", r.sensor_issues.length], ["Active field teams", Object.values(st.teams).filter((t: any) => !t.free).length], ["Open maintenance actions", r.leaks.filter((l: any) => l.workflow.startsWith("PENDING")).length]];
  return (<><div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">{k.map(([a, b]) => <div key={a} className="bg-white border rounded-xl p-3"><div className="text-2xl font-bold">{b}</div><div className="text-xs text-slate-500">{a}</div></div>)}</div>
    <Card t="Summary">{r.summary.map((s: string) => <div key={s}>{s}</div>)}</Card><Flow s={r.series["DMA-B"]} title="DMA-B flow vs forecast (water-loss trend)" /></>);
}
function NetConfig() {
  const [n, setN] = useState<any>(null); useEffect(() => { j("/api/network").then(setN); }, []); if (!n) return null;
  return (<><Card t="Pipelines (unique IDs)"><Table head={["Pipe", "From", "To", "Status"]} rows={n.pipes.map((p: any) => [p.pipe, p.from.join(", "), p.to.join(", "), p.status])} /></Card>
    <Card t="Nodes: reservoir, junctions, pressure sensors"><Table head={["ID", "Type", "Status"]} rows={n.nodes.map((d: any) => [d.id, d.kind, d.status])} /></Card>
    <Card>Assets are defined in the backend topology (read-only here). Field teams can be added on the Field Operations page.</Card></>);
}
function MapPage() {
  const { r } = useR(); const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!ref.current || !r) return; let map: L.Map | null = null, dead = false;
    j("/api/network").then(n => { if (dead || !ref.current) return; map = L.map(ref.current).setView([16.5062, 80.648], 13);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap" }).addTo(map);
      const col: any = { normal: "green", suspected_leak: "red", sensor_problem: "orange" };
      n.pipes.forEach((p: any) => L.polyline([p.from, p.to], { color: col[p.status], weight: 6 }).bindPopup(`${p.pipe} - ${p.status}`).addTo(map!));
      n.nodes.forEach((d: any) => L.circleMarker(d.pos, { radius: 7, color: col[d.status] }).bindPopup(`${d.id} (${d.kind}) - ${d.status}`).addTo(map!)); });
    return () => { dead = true; map && map.remove(); }; }, [r]);
  return <Card t="Network map: green normal, red suspected leak, orange sensor problem"><div ref={ref} style={{ height: 500 }} /></Card>;
}
function Sensors() {
  const { r } = useR(); if (!r) return null; const bad = new Set(r.sensor_issues.map((i: any) => i.zone));
  return (<><Card t="Sensor health by zone"><Table head={["Zone", "Latest flow m³/h", "Forecast m³/h", "Pressure drop (bar)", "Health"]} rows={zones(r).map(([z, a]) => [z, r.series[z].actual.at(-1), r.series[z].forecast.at(-1), a.pressure_drop_bar ?? "n/a", bad.has(z) ? "⚠ sensor issue" : "OK"])} /></Card>
    <Card t="Validation findings">{r.sensor_issues.length ? <Table head={["Zone", "Time", "Issue", "Value", "Action"]} rows={r.sensor_issues.map((i: any) => [i.zone, i.ts, i.issue, i.value, i.action])} /> : "No invalid readings."}</Card>
    {Object.keys(r.series).map(z => <Flow key={z} s={r.series[z]} title={`${z} flow`} />)}</>);
}
function Forecast() {
  const { r } = useR(); if (!r) return null;
  return (<><Card t="Model: RandomForest, 50-day train / 10-day validation"><Table head={["Zone", "MAE", "RMSE", "MAPE %"]} rows={Object.entries(r.forecast_metrics).map(([z, m]: any) => [z, m.MAE, m.RMSE, m["MAPE_%"]])} /></Card>
    {Object.keys(r.series).map(z => <Flow key={z} s={r.series[z]} title={`${z}: forecast vs observed`} />)}</>);
}
function Leaks() {
  const { r, reload } = useR(); if (!r) return null;
  return (<>{!r.leaks.length && <Card>No active leak hypotheses.</Card>}{r.leaks.map((l: any) => <Card key={l.leak_id} t={`${l.leak_id} - ${l.zone} - ${l.status} (${l.confidence}, ${l.confidence_score})`}>
    <div>Suspected section: {l.suspected_section}</div><div>Estimated start: {l.est_start}</div><div className="mt-1">Supporting: {l.evidence.join("; ")}</div><div>Contradicting: {l.contradicting.join("; ") || "none"}</div>
    <div>Est. loss {l.est_loss_m3} m³ ({l.est_rate_m3h} m³/h). {l.loss_assumption}</div><div>Verification: {l.verification}</div><div>Workflow: {l.workflow}</div>
    <div className="text-xs text-slate-500">History: {l.history.map((h: any) => `${h.hours_of_data}h:${h.status}`).join(" → ")}</div>
    <Btn onClick={() => act(`/api/approve/${l.leak_id}/${l.plan.suggested_team}`, reload)}>Approve inspection</Btn><Btn onClick={() => act(`/api/repair/${l.leak_id}`, reload)}>Record repair + validate</Btn></Card>)}
    <Btn onClick={async () => alert(JSON.stringify(await j("/api/reassess"), null, 1))}>Reassess with new data (TC-07)</Btn></>);
}
function Analytics() {
  const { r } = useR(); if (!r) return null; const d = zones(r).map(([zone, a]) => ({ zone, flow_z: a.max_z, pressure_drop: a.pressure_drop_bar ?? 0 }));
  return (<><Bars data={d} keys={["flow_z", "pressure_drop"]} title="Flow z-score and pressure drop by zone" />
    <Card t="Minimum night flow"><Table head={["Zone", "Night flow now", "Baseline", "Flow anomaly", "Pressure anomaly", "Night-flow anomaly", "Upstream stable"]} rows={zones(r).map(([z, a]) => [z, a.mnf_now, a.mnf_baseline, String(a.flow_anomaly), String(a.pressure_anomaly), String(a.mnf_anomaly), String(a.upstream_stable)])} /></Card></>);
}
function Balance() {
  const { r } = useR(); if (!r) return null; const d = Object.entries(r.water_balance).map(([zone, w]: any) => ({ zone, inflow: w.inflow_m3, expected: w.expected_consumption_m3 }));
  return (<><Bars data={d} keys={["inflow", "expected"]} title="Supplied vs expected consumption (m³)" /><Card t="Zone water balance"><Table head={["Zone", "Inflow m³", "Expected m³", "Unexplained m³", "Difference %"]} rows={Object.entries(r.water_balance).map(([z, w]: any) => [z, w.inflow_m3, w.expected_consumption_m3, w.unexplained_m3, w.pct_difference])} /><p className="text-xs mt-2">Simplified balance; full NRW needs unbilled use, apparent losses and meter error.</p></Card></>);
}
function Field() {
  const { r, reload } = useR(); const [st, setSt] = useState<any>({ teams: {} }); const load = () => j("/api/state").then(setSt); useEffect(() => { load(); }, [r]);
  return (<Card t="Field teams"><Table head={["Team", "Skills", "Availability"]} rows={Object.entries(st.teams).map(([id, t]: any) => [id, t.skills.join(", "), t.free ? "Available" : "Assigned"])} />
    <Btn onClick={async () => { const id = prompt("Team ID, e.g. T3"); if (id) { await j(`/api/teams/${id}?skills=acoustic`, "POST"); load(); } }}>Add team</Btn></Card>);
}
function Maintenance() {
  const { r, reload } = useR(); if (!r) return null;
  return (<Card t="Prioritized inspection plans (score = 100 × weighted factors)">{!r.leaks.length ? "Nothing to plan." : <Table head={["Leak", "Zone", "Priority", "Factors", "Inspection", "Team", "Action"]} rows={r.leaks.map((l: any) => [l.leak_id, l.zone, l.plan.priority_score, JSON.stringify(l.plan.factors), l.plan.inspection, l.plan.suggested_team, <Btn onClick={() => act(`/api/approve/${l.leak_id}/${l.plan.suggested_team}`, reload)}>Approve</Btn>])} />}</Card>);
}
function AiOps() {
  const { r } = useR(); if (!r) return null;
  return (<><Card t="Agent execution order"><div className="flex flex-wrap gap-2">{r.trace.map((a: string, i: number) => <span key={a} className="px-2 py-1 bg-blue-100 rounded text-sm">{i + 1}. {a}</span>)}</div></Card>
    {([["Agent 1 validation", r.sensor_issues], ["Agent 2 forecast metrics", r.forecast_metrics], ["Agent 3 anomaly scores", r.anomalies], ["Agent 4 leak hypotheses", r.leaks], ["Agent 5 water balance", r.water_balance], ["Agent 8 reviewer feedback", r.review], ["Agent 7 coordinator summary", r.summary]] as [string, any][]).map(([t, v]) => <Card key={t}><details><summary className="cursor-pointer font-semibold">{t}</summary><pre className="text-xs overflow-x-auto mt-2">{JSON.stringify(v, null, 1)}</pre></details></Card>)}</>);
}
function Alerts() {
  const { r } = useR(); if (!r) return null; const rows: any[][] = [];
  r.leaks.forEach((l: any) => rows.push([l.confidence === "High" ? "HIGH" : "MEDIUM", "Leak", `${l.leak_id} in ${l.zone}: ${l.status}`]));
  r.sensor_issues.forEach((i: any) => rows.push(["MEDIUM", "Sensor", `${i.zone}: ${i.issue} (${i.value})`]));
  zones(r).forEach(([z, a]) => { if (a.flow_anomaly) rows.push(["INFO", "Flow", `${z}: flow above forecast`]); if (a.pressure_anomaly) rows.push(["INFO", "Pressure", `${z}: pressure drop ${a.pressure_drop_bar} bar`]); });
  return <Card t="Active alerts">{rows.length ? <Table head={["Severity", "Type", "Message"]} rows={rows} /> : "No active alerts."}</Card>;
}
function Reports() {
  const { r, setR } = useR(); if (!r) return null;
  return (<><Card t="Water network report">{r.summary.map((s: string) => <div key={s}>{s}</div>)}<Btn onClick={() => window.open(API + "/api/report.pdf")}>Download PDF report</Btn><Btn onClick={() => window.open(API + "/api/sample.csv")}>Sample sensor CSV</Btn></Card>
    <Card t="Analyse your own sensor CSV (ts,zone,flow,p_up,p_dn)"><input type="file" accept=".csv" onChange={async e => { const f = new FormData(); f.append("file", e.target.files![0]); setR(await (await fetch(API + "/api/upload", { method: "POST", body: f })).json()); }} /></Card></>);
}

const PAGES: Record<string, () => JSX.Element | null> = { "Water Operations Dashboard": Dashboard, "Network Configuration": NetConfig, "Live Network Map": MapPage, "Sensor Monitoring": Sensors, "Demand Forecasting": Forecast, "Leak Detection Center": Leaks,
  "Pressure & Flow Analytics": Analytics, "Water Balance": Balance, "Field Operations": Field, "Maintenance Planning": Maintenance, "AI Operations Center": AiOps, "Alert Center": Alerts, "Reports": Reports };

export default function App() {
  const [scen, setScen] = useState("leak"); const [r, setR] = useState<any>(null); const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(decodeURIComponent(location.hash.slice(1)) || "Water Operations Dashboard");
  const reload = (s = scen) => { setBusy(true); j(`/api/run?scenario=${s}`).then(setR).catch(() => alert("Backend not reachable (free server may be waking up). Retry in a minute.")).finally(() => setBusy(false)); };
  useEffect(() => { reload(scen); }, [scen]); useEffect(() => { location.hash = page; }, [page]);
  const P = PAGES[page] || Dashboard;
  return (<Ctx.Provider value={{ r, setR, scen, reload: () => reload() }}><div className="flex min-h-screen bg-slate-100 text-slate-900">
    <aside className="w-56 bg-slate-900 text-slate-100 p-3 shrink-0"><div className="font-bold mb-3">Water Ops Center</div>{Object.keys(PAGES).map(p => <button key={p} onClick={() => setPage(p)} className={`block w-full text-left text-sm px-2 py-1 rounded mb-1 ${p === page ? "bg-blue-600" : "hover:bg-slate-700"}`}>{p}</button>)}</aside>
    <main className="flex-1 p-4 min-w-0"><div className="flex items-center gap-3 mb-4"><h1 className="text-xl font-bold flex-1">{page}</h1><label className="text-sm">Scenario <select className="border rounded p-1" value={scen} onChange={e => setScen(e.target.value)}>{SCEN.map(s => <option key={s}>{s}</option>)}</select></label>{busy && <span className="text-sm text-slate-500">Loading… (free server may take up to a minute to wake)</span>}</div><P /></main></div></Ctx.Provider>);
}
