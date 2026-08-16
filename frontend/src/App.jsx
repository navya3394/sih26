import React, { useEffect, useMemo, useState } from "react";
import {
  Search, ShieldCheck, ClipboardList, BarChart3, FileClock, CheckCircle2,
  AlertTriangle, Lock, Globe2, Landmark, ChevronRight, Send, Users, FileCheck2,
  Building2, LogOut, Eye, Filter, RefreshCcw
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const roleConfig = {
  clinic_doctor: { title: "Clinic Doctor", subtitle: "Clinical terminology and dual-coding workspace", icon: Users },
  insurance_reviewer: { title: "Insurance Reviewer", subtitle: "Claims review and coding-readiness workspace", icon: FileCheck2 },
  government_analyst: { title: "Government Analyst", subtitle: "National AYUSH morbidity intelligence", icon: Landmark },
};

function apiFetch(path, options = {}, token) {
  return fetch(`${API}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) } }).then(async (r) => {
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || "Request failed");
    return data;
  });
}

function Login({ onLogin }) {
  const [role, setRole] = useState("clinic_doctor");
  const [username, setUsername] = useState("doctor.nodal");
  const [password, setPassword] = useState("AyuSetu@2026");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function signIn() {
    setLoading(true);
    try {
      setError("");
      const data = await apiFetch("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      onLogin(data);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }
  return (
    <div className="login-page">
      <div className="tricolor" />
      <div className="gov-strip"><div className="shell gov-strip-inner"><span>भारत सरकार · Government of India</span><span>Ministry of Ayush</span></div></div>
      <main className="login-shell shell">
        <div className="brand-large"><span className="chakra">◉</span><div><div className="brand-title">AyuSetu</div><div className="brand-sub">NAMASTE · ICD-11 TM2 Interoperability Service</div></div></div>
        <div className="login-card">
          <div className="eyebrow">Secure access</div>
          <h1>Select your workspace</h1>
          <p className="muted-text">Access is determined by your assigned role.</p>
          <div className="role-grid">
            {Object.entries(roleConfig).map(([key, value]) => {
              const Icon = value.icon;
              return <button key={key} className={`role-option ${role === key ? "selected" : ""}`} onClick={() => { setRole(key); if(key==="clinic_doctor"){setUsername("doctor.nodal");setPassword("AyuSetu@2026")} if(key==="insurance_reviewer"){setUsername("review.officer");setPassword("Claims@2026")} if(key==="government_analyst"){setUsername("analyst.gov");setPassword("Policy@2026")} }}><Icon size={22}/><div><strong>{value.title}</strong><span>{value.subtitle}</span></div></button>;
            })}
          </div>
          <div className="login-fields"><label>Access ID<input value={username} onChange={e=>setUsername(e.target.value)}/></label><label>Access key<input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label></div>{error&&<div className="login-error">{error}</div>}<button className="primary-btn full" onClick={signIn} disabled={loading}><Lock size={16}/>{loading ? "Signing in…" : "Continue securely"}</button>
        </div>
      </main>
    </div>
  );
}

function Header({ profile, onLogout, active, setActive }) {
  const items = profile.role === "clinic_doctor"
    ? [["workspace", "Clinician Workspace", Search], ["problems", "Problem List", ClipboardList], ["audit", "Audit Trail", FileClock]]
    : profile.role === "insurance_reviewer"
    ? [["claims", "Claims Review", FileCheck2], ["audit", "Audit Trail", FileClock]]
    : [["dashboard", "National Dashboard", BarChart3], ["audit", "Audit Trail", FileClock]];
  return <header><div className="tricolor"/><div className="gov-strip"><div className="shell gov-strip-inner"><span>भारत सरकार · Government of India</span><span><Landmark size={13}/> Ministry of Ayush</span></div></div><div className="header-main"><div className="shell header-inner"><div className="brand"><span className="chakra-mark">◉</span><div><div className="brand-title">AyuSetu</div><div className="brand-sub">NAMASTE · ICD-11 TM2 Interoperability Service</div></div></div><div className="header-actions"><span className="role-chip">{profile.title}</span><button className="logout-btn" onClick={onLogout}><LogOut size={14}/> Sign out</button></div></div></div><nav className="tabnav"><div className="shell tabnav-inner">{items.map(([id,label,Icon])=><button key={id} className={active===id?"tab active":"tab"} onClick={()=>setActive(id)}><Icon size={16}/>{label}</button>)}</div></nav></header>;
}

function ConfidenceBadge({ value, status }) {
  if (status === "verified") return <span className="confidence success">Verified mapping</span>;
  if (value === null || value === undefined) return <span className="confidence neutral">No TM2 mapping</span>;
  const pct = Math.round(value);
  const cls = pct < 50 ? "danger" : pct < 75 ? "warning" : "success";
  return <span className={`confidence ${cls}`}>{pct}% confidence</span>;
}

function ConfirmationDialog({ term, onCancel, onConfirm }) {
  const pct = Math.round(term.mappingConfidencePercent || 0);
  return <div className="modal-backdrop"><div className="modal-card"><div className="modal-icon"><AlertTriangle size={22}/></div><div className="eyebrow">Low-confidence mapping</div><h3>Confirm this diagnosis selection</h3><p>The mapping confidence is <strong>{pct}%</strong>, below the 50% review threshold. Please confirm that you want to continue with this choice.</p><div className="confirm-detail"><strong>{term.term}</strong><span>{term.namasteCode} → {term.tm2Code || "No TM2 mapping"}</span></div><div className="modal-actions"><button className="secondary-btn" onClick={onCancel}>Cancel</button><button className="primary-btn" onClick={onConfirm}>Confirm selection</button></div></div></div>;
}

function PatientBar(){return <div className="patient-bar"><div><small>Patient</small><strong>Rohan Verma · M · 42y</strong></div><div><small>ABHA ID</small><strong>XX-XXXX-XXXX-1234</strong></div><div><small>Encounter</small><strong>OPD · Ayurveda · #OPD-88231</strong></div><div><small>Facility</small><strong>District AYUSH Hospital, Jodhpur</strong></div></div>}

function Workspace({ token, onAdded }) {
  const [query,setQuery]=useState(""); const [results,setResults]=useState([]); const [selected,setSelected]=useState(null); const [pending,setPending]=useState(null); const [adding,setAdding]=useState(false);
  useEffect(()=>{const h=setTimeout(()=>{if(query.trim()) apiFetch(`/terminology/search?q=${encodeURIComponent(query)}&limit=8`,{},token).then(d=>setResults(d.results||[])).catch(()=>setResults([])); else setResults([]);},180);return()=>clearTimeout(h)},[query,token]);
  async function pick(term){ if(term.hasMapping && term.mappingConfidencePercent < 50){setPending(term);return;} setSelected(term); }
  async function add(term){setAdding(true);try{const bundle={resourceType:"Bundle",type:"transaction",entry:[{resource:{resourceType:"Patient",id:"patient-rohan-verma"}},{resource:{resourceType:"Encounter",id:"enc-OPD-88231"}},{resource:{resourceType:"Condition",id:`cond-${term.namasteCode}`,code:{coding:[{system:"https://namaste.ayush.gov.in/fhir/CodeSystem/namaste",code:term.namasteCode,display:term.term},{system:"http://id.who.int/icd/release/11/2026-01/tm2",code:term.tm2Code,display:term.tm2Title},...(term.bioCode?[{system:"http://id.who.int/icd/release/11/2026-01/mms",code:term.bioCode,display:term.bioTitle}]:[])]}}}]}; await apiFetch("/bundle",{method:"POST",body:JSON.stringify({bundle,consent_reference:"ABDM-CONSENT-OPD-88231"})},token); onAdded(term);} finally{setAdding(false)}}
  return <div className="shell page"><div className="eyebrow">Clinical workspace</div><h1>Record a dual-coded diagnosis</h1><p className="page-desc">Search standardized AYUSH terminology and review its ICD-11 mapping before committing it to the patient record.</p><PatientBar/><div className="search-area"><Search size={19}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search by diagnosis, transliteration, or clinical description"/>{query&&<span className="result-count">{results.length}</span>}</div>{results.length>0&&<div className="suggestions">{results.map(t=><button key={t.id} className="suggestion" onClick={()=>pick(t)}><div><strong>{t.term}</strong><span>{t.shortDef}</span></div><div className="suggestion-right"><span className={`system-tag ${t.system.toLowerCase()}`}>{t.system}</span><ConfidenceBadge value={t.mappingConfidencePercent} status={t.mappingStatus}/></div></button>)}</div>}{selected&&<div className="bridge-card"><div className="bridge-top"><div><div className="eyebrow">Terminology mapping</div><h2>{selected.term}</h2><p>{selected.shortDef}</p></div><span className={`system-tag ${selected.system.toLowerCase()}`}>{selected.system}</span></div><div className="mapping-grid"><div className="mapping-node"><small>NAMASTE</small><strong>{selected.namasteCode}</strong><span>{selected.term}</span></div><div className="mapping-arrow"><ChevronRight size={22}/><ConfidenceBadge value={selected.mappingConfidencePercent} status={selected.mappingStatus}/></div><div className="mapping-node"><small>ICD-11 · TM2</small><strong>{selected.tm2Code || "No mapping"}</strong><span>{selected.tm2Title || "No authoritative TM2 mapping is currently recorded for this terminology entry."}</span></div></div>{selected.bioCode&&<div className="secondary-map"><span>Biomedical reference</span><strong>{selected.bioCode}</strong><span>{selected.bioTitle}</span></div>} {!selected.bioCode&&<div className="clinical-alert"><AlertTriangle size={17}/><span>No safe biomedical equivalent is recorded for this terminology entry.</span></div>}<div className="bridge-footer"><div><small>Claims readiness</small><strong className={selected.claimsReady?"good-text":"warn-text"}>{selected.claimsReady?"Claims-ready":"Needs review"}</strong></div><button className="primary-btn" onClick={()=>add(selected)} disabled={adding||!selected.tm2Code}><Send size={15}/>{adding?"Saving…":"Add to problem list"}</button></div></div>}{pending&&<ConfirmationDialog term={pending} onCancel={()=>setPending(null)} onConfirm={()=>{setSelected(pending);setPending(null)}}/>}</div>
}

function ProblemList({ token }){const [rows,setRows]=useState([]);useEffect(()=>{apiFetch('/conditions',{},token).then(setRows).catch(()=>setRows([]))},[token]);return <div className="shell page"><div className="eyebrow">Problem list</div><h1>Encounter problem list</h1><p className="page-desc">Dual-coded conditions recorded for the current patient encounter.</p><PatientBar/><div className="table-card"><table><thead><tr><th>Terminology</th><th>NAMASTE</th><th>ICD-11 TM2</th><th>Consent</th><th>Recorded</th></tr></thead><tbody>{rows.length===0?<tr><td colSpan="5" className="empty-cell">No conditions recorded yet.</td></tr>:rows.map(r=><tr key={r.id}><td><strong>{r.resource.entry?.find(e=>e.resource?.resourceType==='Condition')?.resource?.code?.coding?.[0]?.display||'Condition'}</strong></td><td className="mono">{r.resource.entry?.find(e=>e.resource?.resourceType==='Condition')?.resource?.code?.coding?.[0]?.code}</td><td className="mono">{r.resource.entry?.find(e=>e.resource?.resourceType==='Condition')?.resource?.code?.coding?.[1]?.code}</td><td>{r.consentReference}</td><td>{new Date(r.createdAt).toLocaleString('en-IN')}</td></tr>)}</tbody></table></div></div>}

function Claims({ token }){const [rows,setRows]=useState([]);const [filter,setFilter]=useState('All');const load=()=>apiFetch('/claims',{},token).then(setRows);useEffect(()=>{load()},[token]);const shown=rows.filter(r=>filter==='All'||r.status===filter);return <div className="shell page"><div className="eyebrow">Insurance review</div><h1>Claims coding review</h1><p className="page-desc">Review dual-coded AYUSH diagnoses for interoperability and claims readiness.</p><div className="filter-row"><button className={filter==='All'?'filter active':'filter'} onClick={()=>setFilter('All')}><Filter size={14}/> All</button><button className={filter==='Claims-ready'?'filter active':'filter'} onClick={()=>setFilter('Claims-ready')}>Claims-ready</button><button className={filter==='Needs review'?'filter active':'filter'} onClick={()=>setFilter('Needs review')}>Needs review</button><button className="filter" onClick={load}><RefreshCcw size={14}/> Refresh</button></div><div className="table-card"><table><thead><tr><th>Claim</th><th>Diagnosis</th><th>Codes</th><th>Confidence</th><th>Status</th></tr></thead><tbody>{shown.map(r=><tr key={r.claimId}><td><strong>{r.claimId}</strong><small>{r.provider}</small></td><td>{r.diagnosis}<small>{r.encounter}</small></td><td className="mono">{r.namasteCode}<br/>{r.tm2Code}</td><td><ConfidenceBadge value={r.confidence}/></td><td><span className={`status-chip ${r.status==='Claims-ready'?'success':'warning'}`}>{r.status}</span></td></tr>)}</tbody></table></div></div>}

function Dashboard({ token }){const [data,setData]=useState(null);useEffect(()=>{apiFetch('/analytics/summary',{},token).then(setData)},[token]);if(!data)return <div className="shell page"><div className="loading">Loading national dashboard…</div></div>;return <div className="shell page"><div className="eyebrow">Ministry of Ayush · National analytics</div><h1>National morbidity intelligence</h1><p className="page-desc">Aggregated dual-coded AYUSH encounters for policy monitoring and service planning.</p><div className="stats-grid"><div className="stat-card"><strong>{data.terminologyRecords.toLocaleString()}</strong><span>Indexed terminology records</span></div><div className="stat-card"><strong>{data.recordedBundles.toLocaleString()}</strong><span>Encounter bundles recorded</span></div><div className="stat-card"><strong>18,742</strong><span>August dual-coded encounters</span></div><div className="stat-card"><strong>88%</strong><span>National dual-coding coverage</span></div></div><div className="chart-grid"><div className="panel"><div className="panel-title">Monthly encounters</div><ResponsiveContainer width="100%" height={280}><LineChart data={data.monthlyTrend}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="month"/><YAxis/><Tooltip/><Line type="monotone" dataKey="encounters" stroke="#163a5f" strokeWidth={2.5}/></LineChart></ResponsiveContainer></div><div className="panel"><div className="panel-title">Top terminology categories</div><ResponsiveContainer width="100%" height={280}><BarChart data={data.topCategories} layout="vertical"><CartesianGrid strokeDasharray="3 3"/><XAxis type="number"/><YAxis type="category" dataKey="name" width={150}/><Tooltip/><Bar dataKey="value" fill="#163a5f"/></BarChart></ResponsiveContainer></div></div><div className="table-card"><div className="panel-title inside">State-wise coverage</div><table><thead><tr><th>State</th><th>Encounters</th><th>Dual coding</th><th>Claims-ready</th><th>Facilities</th></tr></thead><tbody>{data.states.map(s=><tr key={s.state}><td><strong>{s.state}</strong></td><td>{s.encounters.toLocaleString()}</td><td>{s.dual}%</td><td>{s.claims}%</td><td>{s.facilities}</td></tr>)}</tbody></table></div></div>}

function Audit({ token }){const [rows,setRows]=useState([]);useEffect(()=>{apiFetch('/audit',{},token).then(setRows)},[token]);return <div className="shell page"><div className="eyebrow">Audit trail</div><h1>Access and activity record</h1><p className="page-desc">Timestamped records of terminology searches, translations, bundle submissions, and access events.</p><div className="table-card"><table><thead><tr><th>Time</th><th>Actor</th><th>Role</th><th>Action</th><th>Detail</th></tr></thead><tbody>{rows.length===0?<tr><td colSpan="5" className="empty-cell">No activity recorded yet.</td></tr>:rows.map(r=><tr key={r.id}><td>{new Date(r.timestamp).toLocaleString('en-IN')}</td><td><strong>{r.actor}</strong></td><td>{r.role}</td><td><span className="status-chip info">{r.action}</span></td><td>{r.detail}</td></tr>)}</tbody></table></div></div>}

function App(){const [session,setSession]=useState(()=>JSON.parse(localStorage.getItem('ayusetu-session')||'null'));const [active,setActive]=useState(null);useEffect(()=>{if(session){const defaults=session.profile.role==='clinic_doctor'?'workspace':session.profile.role==='insurance_reviewer'?'claims':'dashboard';setActive(defaults)}},[session]);function save(data){localStorage.setItem('ayusetu-session',JSON.stringify(data));setSession(data)}function logout(){localStorage.removeItem('ayusetu-session');setSession(null)}if(!session)return <Login onLogin={save}/>;return <><Header profile={session.profile} onLogout={logout} active={active} setActive={setActive}/>{active==='workspace'&&<Workspace token={session.access_token} onAdded={()=>setActive('problems')}/>} {active==='problems'&&<ProblemList token={session.access_token}/>} {active==='claims'&&<Claims token={session.access_token}/>} {active==='dashboard'&&<Dashboard token={session.access_token}/>} {active==='audit'&&<Audit token={session.access_token}/>}</>}

export default App;
