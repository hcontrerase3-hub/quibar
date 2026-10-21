import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
export const sectors = ['Santa Bárbara', 'Huequecura', 'Ralco'];
const categories = ['Mirador', 'Naturaleza', 'Patrimonio', 'Plaza', 'Actividad', 'Cultura'];
type Interest = { id?: string; name: string; category: string; commune: string; sector: string; description: string; latitude: number | null; longitude: number | null; access: string; hours: string; source: string; access_verified: boolean; status: string };
type Station = { name: string; latitude: number | null; longitude: number | null; source: string; verified: boolean };
type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
const blank: Interest = { name: '', category: 'Mirador', commune: 'Santa Bárbara', sector: 'Santa Bárbara', description: '', latitude: null, longitude: null, access: '', hours: '', source: '', access_verified: false, status: 'Pendiente' };
export default function TerritoryAdmin({ api, administrator, communes }: { api: Api; administrator: boolean; communes: string[] }) {
  const [rows, setRows] = useState<Interest[]>([]);
  const [draft, setDraft] = useState<Interest | null>(null);
  const [station, setStation] = useState<Station | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { let live = true; Promise.all([api<Interest[]>('/interests'), api<Station>('/station')]).then(([r, s]) => { if (live) { setRows(r); setStation(s); } }).catch(e => { if (live) setError(e.message); }); return () => { live = false; }; }, []);
  async function save(e: FormEvent, isStation = false) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      if (isStation && station) { setStation(await api<Station>('/station', { method: 'PUT', body: JSON.stringify(station) })); setMessage('Ubicación del tótem actualizada.'); }
      else if (draft) { const saved = await api<Interest>(draft.id ? `/interests/${draft.id}` : '/interests', { method: draft.id ? 'PUT' : 'POST', body: JSON.stringify(draft) }); setDraft(saved); setRows(await api<Interest[]>('/interests')); setMessage('Lugar guardado. Solo los aprobados con acceso verificado se muestran.'); }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  function edit(key: keyof Interest, value: unknown) { setDraft(d => d ? { ...d, [key]: value } : null); }
  return <>
    {error && <p role="alert" className="admin-error">{error}</p>}{message && <p role="status" className="admin-notice">{message}</p>}
    <div className="admin-workspace"><aside className="admin-list"><h1>Atractivos del circuito</h1><button onClick={() => setDraft({ ...blank })}>+ Nuevo lugar</button><div className="admin-business-list">{rows.map(r => <button key={r.id} onClick={() => setDraft({ ...r, status: !administrator && r.status === 'Aprobado' ? 'Pendiente' : r.status })}><strong>{r.name}</strong><span>{r.sector} · {r.category}</span><small>{r.status}</small></button>)}</div></aside>
    <section className="admin-editor">{draft ? <form onSubmit={e => void save(e)}><div className="admin-editor-heading"><h2>{draft.name || 'Nuevo punto de interés'}</h2><button className="admin-primary" disabled={busy}>Guardar lugar</button></div><fieldset disabled={busy}><legend>Información y acceso verificados</legend><div className="admin-fields">
      {(['name', 'description', 'access', 'source', 'hours'] as const).map(key => <label className="wide" key={key}>{{name:'Nombre',description:'Descripción',access:'Cómo acceder',source:'Fuente de verificación',hours:'Horarios (opcional)'}[key]}<input required={key !== 'hours'} minLength={key === 'name' ? 2 : key === 'hours' ? 0 : 5} maxLength={key === 'description' ? 4000 : key === 'name' ? 150 : key === 'hours' ? 255 : 1000} value={draft[key]} onChange={e => edit(key, e.target.value)} /></label>)}
      <label>Sector<select value={draft.sector} onChange={e => edit('sector', e.target.value)}>{sectors.map(s => <option key={s}>{s}</option>)}</select></label><label>Comuna<select value={draft.commune} onChange={e => edit('commune', e.target.value)}>{communes.map(s => <option key={s}>{s}</option>)}</select></label>
      <label>Tipo de lugar<select value={draft.category} onChange={e => edit('category', e.target.value)}>{categories.map(s => <option key={s}>{s}</option>)}</select></label>
      {(['latitude','longitude'] as const).map(key => <label key={key}>{key === 'latitude' ? 'Latitud' : 'Longitud'}<input required type="number" step="any" min={key === 'latitude' ? -90 : -180} max={key === 'latitude' ? 90 : 180} value={draft[key] ?? ''} onChange={e => edit(key, e.target.value === '' ? null : Number(e.target.value))} /></label>)}
      <label>Estado<select value={draft.status} onChange={e => edit('status', e.target.value)}>{['Pendiente', ...(administrator ? ['Aprobado'] : []), 'Suspendido'].map(s => <option key={s}>{s}</option>)}</select></label><label className="wide"><span><input type="checkbox" checked={draft.access_verified} onChange={e => edit('access_verified', e.target.checked)} /> He verificado la ubicación y el acceso descrito</span></label>
    </div></fieldset></form> : <p>Registra lugares reales de Santa Bárbara, Huequecura y Ralco. No se generan ubicaciones de ejemplo.</p>}</section></div>
    {station && <section className="admin-editor"><form onSubmit={e => void save(e, true)}><h2>Ubicación de este tótem</h2><p>Las rutas parten de esta ubicación. Solo un administrador puede cambiarla.</p><fieldset disabled={!administrator || busy}><div className="admin-fields"><label>Nombre<input required minLength={2} maxLength={150} value={station.name} onChange={e => setStation({ ...station, name:e.target.value })} /></label>{(['latitude','longitude'] as const).map(key => <label key={key}>{key === 'latitude' ? 'Latitud del tótem' : 'Longitud del tótem'}<input required type="number" step="any" value={station[key] ?? ''} onChange={e => setStation({ ...station, [key]: e.target.value === '' ? null : Number(e.target.value) })} /></label>)}<label>Fuente de verificación<input required minLength={5} maxLength={1000} value={station.source} onChange={e => setStation({ ...station, source:e.target.value })} /></label><label><span><input type="checkbox" checked={station.verified} onChange={e => setStation({ ...station, verified:e.target.checked })} /> Ubicación verificada</span></label></div><button className="admin-primary">Guardar ubicación</button></fieldset></form></section>}
  </>;
}
