import TerritoryAdmin, { sectors } from "./territory-admin";
import AdminLocationPicker from "./admin-location-picker";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import "./admin.css";

type Session = { id: number; name: string; email: string; role: string; csrf: string };
type Photo = { id: number; url: string; alt: string; cover: boolean; order: number };
type Business = {
  sector?: string; location_source?: string; location_verified?: boolean; id?: string; name: string; category: string; commune: string; area: string; summary: string;
  description: string; offerings: string[]; hours: string; keywords: string; visual: string;
  status: "Pendiente" | "Aprobado" | "Suspendido"; latitude: number | null; longitude: number | null;
  whatsapp: string; legal_name: string; tax_id: string; featured: boolean; demo: boolean; photos: Photo[];
};
type User = { id?: number; name: string; email: string; role: string; active: boolean; password?: string };
type Audit = { id: number; user_id: number; action: string; at: string; detail: object };
type Metric = { event: string; count: number; average_ms: number | null };
const blank: Business = { name: "", category: "Gastronomía", commune: "Santa Bárbara", sector: "Santa Bárbara", location_source: "", location_verified: false, area: "", summary: "", description: "",
  offerings: [""], hours: "", keywords: "", visual: "shop", status: "Pendiente", latitude: null, longitude: null,
  whatsapp: "", legal_name: "", tax_id: "", featured: false, demo: false, photos: [] };
const blankUser: User = { name: "", email: "", role: "Operador Territorial", active: true, password: "" };

type FieldIssue = { control: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement; label: string; message: string };
function businessIssues(form: HTMLFormElement): FieldIssue[] {
  const issues: FieldIssue[] = [];
  for (const control of Array.from(form.elements)) {
    if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement) || !control.willValidate) continue;
    const value = control.value.trim();
    let message = "";
    if (control.required && !value) message = "Completa este campo.";
    else if ("minLength" in control && value && control.minLength > 0 && value.length < control.minLength) message = `Escribe al menos ${control.minLength} caracteres.`;
    else if (!control.validity.valid) {
      if (control.validity.rangeUnderflow && control instanceof HTMLInputElement) message = `El valor mínimo es ${control.min}.`;
      else if (control.validity.rangeOverflow && control instanceof HTMLInputElement) message = `El valor máximo es ${control.max}.`;
      else if (control.validity.patternMismatch && "placeholder" in control && control.placeholder) message = `Usa el formato ${control.placeholder}.`;
      else message = "Revisa el valor de este campo.";
    }
    if (message) issues.push({ control, label: control.labels?.[0]?.firstChild?.textContent?.trim() || "Campo", message });
  }
  return issues;
}

export default function Admin() {
  const [user, setUser] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("catalog");
  const [rows, setRows] = useState<Business[]>([]);
  const [draft, setDraft] = useState<Business | null>(null);
  const businessForm = useRef<HTMLFormElement>(null);
  const [validationAttempted, setValidationAttempted] = useState(false);
  const [fieldIssues, setFieldIssues] = useState<FieldIssue[]>([]);
  const [lookups, setLookups] = useState({ communes: ["Santa Bárbara", "Alto Biobío", "Quilaco"], categories: ["Gastronomía", "Alojamiento", "Turismo", "Artesanía", "Comercio"] });
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("Todos");
  const [logs, setLogs] = useState<Audit[]>([]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [userDraft, setUserDraft] = useState<User | null>(null);

  async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
    if (user) headers.set("x-csrf-token", user.csrf);
    const response = await fetch(`/api/quibar/admin${path}`, { ...options, headers, credentials: "same-origin", cache: "no-store" });
    if (response.status === 401) { setUser(null); setDraft(null); setRows([]); }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const details = Array.isArray(data.detail) ? data.detail.map((item: { msg?: string }) => item.msg?.replace(/^Value error, /, "")).filter(Boolean).join(" ") : "";
      throw new Error(typeof data.detail === "string" ? data.detail : details || "Revisa los campos y vuelve a intentar.");
    }
    return response.json();
  }
  useEffect(() => {
    fetch("/api/quibar/admin/session", { cache: "no-store" }).then(async response => {
      if (response.ok) setUser(await response.json());
      else if (response.status === 403) setError("El panel solo está disponible en este equipo o en la red privada autorizada.");
    }).catch(() => setError("No fue posible conectar con la API local.")).finally(() => setReady(true));
  }, []);
  useEffect(() => {
    if (!user) return;
    Promise.all([api<Business[]>("/businesses"), api<typeof lookups>("/lookups"), api<Metric[]>("/metrics")])
      .then(([businesses, lists, counts]) => { setRows(businesses); setLookups(lists); setMetrics(counts); })
      .catch(e => setError(e.message));
  }, [user?.id]); // session controls the lifetime of the administrative data

  useEffect(() => {
    setValidationAttempted(false);
    setFieldIssues([]);
  }, [draft?.id, tab]);
  useEffect(() => {
    const form = businessForm.current;
    if (!form) return;
    const issues = validationAttempted ? businessIssues(form) : [];
    setFieldIssues(issues);
    for (const control of Array.from(form.elements)) {
      if (issues.some(issue => issue.control === control)) control.setAttribute("aria-invalid", "true");
      else control.removeAttribute("aria-invalid");
    }
  }, [draft, validationAttempted, tab]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "No fue posible completar la operación."); }
    finally { setBusy(false); }
  }
  function login(event: FormEvent) {
    event.preventDefault();
    run(async () => { const session = await api<Session>("/session", { method: "POST", body: JSON.stringify({ email, password }) }); setUser(session); setPassword(""); });
  }
  function edit(key: keyof Business, value: unknown) {
    setDraft(current => current ? {
      ...current, [key]: value,
      ...((key === "latitude" || key === "longitude") && current[key] !== value ? { location_verified: false } : {}),
    } : null);
  }
  function locate(latitude: number, longitude: number) {
    setDraft(current => current && !busy ? {
      ...current, latitude, longitude,
      location_verified: current.latitude === latitude && current.longitude === longitude ? current.location_verified : false,
    } : current);
  }
  function save(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    const issues = businessIssues(event.currentTarget as HTMLFormElement);
    setValidationAttempted(true);
    setFieldIssues(issues);
    if (issues.length) {
      setError(""); setNotice("");
      issues[0].control.focus();
      return;
    }
    run(async () => {
      const saved = await api<Business>(draft.id ? `/businesses/${draft.id}` : "/businesses", { method: draft.id ? "PUT" : "POST", body: JSON.stringify(draft) });
      setDraft(saved); setRows(await api<Business[]>("/businesses")); setNotice("Ficha guardada. Los cambios aprobados ya están disponibles en el catálogo.");
    });
  }
  async function selectTab(value: string) {
    setTab(value); setError(""); setNotice("");
    try {
      if (value === "audit") setLogs(await api<Audit[]>("/audit"));
      if (value === "metrics") setMetrics(await api<Metric[]>("/metrics"));
      if (value === "users") setUsers(await api<User[]>("/users"));
    } catch (e) { setError((e as Error).message); }
  }
  function updatePhoto(photo: Photo, remove = false) {
    if (!draft?.id) return;
    run(async () => {
      const updated = await api<Business>(`/businesses/${draft.id}/photos/${photo.id}`, {
        method: remove ? "DELETE" : "PUT", ...(remove ? {} : { body: JSON.stringify(photo) }),
      });
      setDraft(updated); setRows(await api<Business[]>("/businesses")); setNotice("Fotografías actualizadas.");
    });
  }

  if (!ready) return <main className="admin-login"><p>Cargando administración…</p></main>;
  if (!user) return <main className="admin-login"><form onSubmit={login} className="admin-login-card">
    <span className="admin-eyebrow">QUÍBAR · ADMINISTRACIÓN LOCAL</span><h1>Gestionar el territorio</h1>
    <p>Acceso para el equipo autorizado. Las fichas aprobadas alimentan el catálogo y el asistente local.</p>
    {error && <p className="admin-error" role="alert">{error}</p>}
    <label>Correo institucional<input required type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} /></label>
    <label>Contraseña<input required type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} /></label>
    <button disabled={busy} className="admin-primary">{busy ? "Ingresando…" : "Ingresar"}</button><a href="/">Volver al tótem</a>
  </form></main>;

  return <main className="admin-shell">
    <header className="admin-header"><a href="/" className="admin-logo">quibar.</a><span>Administración del catálogo</span><div><strong>{user.name}</strong><small>{user.role}</small></div><button disabled={busy} onClick={() => run(async () => { await api("/session", { method: "DELETE" }); setUser(null); setDraft(null); setRows([]); })}>Cerrar sesión</button></header>
    <nav className="admin-tabs" aria-label="Administración">{[["catalog", "Catálogo"], ["territory", "Atractivos y tótem"], ["metrics", "Uso del tótem"], ...(user.role === "Administrador" ? [["audit", "Auditoría"], ["users", "Usuarios"]] : [])].map(([key, label]) => <button key={key} aria-current={tab === key ? "page" : undefined} onClick={() => selectTab(key)}>{label}</button>)}</nav>
    {error && <p className="admin-error" role="alert">{error}</p>}{notice && <p className="admin-notice" role="status">{notice}</p>}
    {tab === "territory" && <TerritoryAdmin api={api} administrator={user.role === "Administrador"} communes={lookups.communes} />}
    {tab === "catalog" && <div className="admin-workspace"><aside className="admin-list"><div className="admin-list-heading"><h1>Fichas comerciales</h1><button disabled={busy} onClick={() => { setDraft({ ...blank, offerings: [""], photos: [] }); setNotice(""); }}>+ Nueva ficha</button></div>
      <label className="sr-only" htmlFor="admin-search">Buscar fichas</label><input id="admin-search" placeholder="Buscar por nombre o comuna" value={search} onChange={e => setSearch(e.target.value)} />
      <label className="sr-only" htmlFor="admin-filter">Estado de moderación</label><select id="admin-filter" value={filter} onChange={e => setFilter(e.target.value)}>{["Todos", "Pendiente", "Aprobado", "Suspendido"].map(s => <option key={s}>{s}</option>)}</select>
      <div className="admin-business-list">{rows.filter(r => (filter === "Todos" || r.status === filter) && `${r.name} ${r.commune}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(row => <button disabled={busy} key={row.id} className={row.id === draft?.id ? "selected" : ""} onClick={() => { setDraft({ ...structuredClone(row), status: user.role !== "Administrador" && row.status === "Aprobado" ? "Pendiente" : row.status }); setNotice(""); }}><strong>{row.name}</strong><span>{row.commune} · {row.category}</span><small className={`status-${row.status}`}>{row.status}{row.demo ? " · Ejemplo" : ""}</small></button>)}</div>
    </aside><section className="admin-editor">{!draft ? <div className="admin-empty"><h2>Un catálogo que representa al territorio</h2><p>Selecciona una ficha para revisarla o crea una nueva. Solo las fichas aprobadas aparecen en el tótem.</p></div> : <>
      <form ref={businessForm} noValidate onSubmit={save}><div className="admin-editor-heading"><div><span className="admin-eyebrow">{draft.id ? "EDITAR FICHA" : "NUEVA FICHA"}</span><h2>{draft.name || "Datos del comercio"}</h2></div><button className="admin-primary" disabled={busy}>{busy ? "Guardando…" : "Guardar ficha"}</button></div>
      {fieldIssues.length > 0 && <div className="admin-validation" role="alert"><strong>No se guardó la ficha. Revisa estos campos:</strong><ul>{fieldIssues.map(issue => <li key={issue.label}><button type="button" onClick={() => issue.control.focus()}>{issue.label}: {issue.message}</button></li>)}</ul></div>}
      <fieldset disabled={busy}><legend>Información pública</legend><div className="admin-fields">
        <label className="wide">Nombre comercial<input required minLength={2} maxLength={150} value={draft.name} onChange={e => edit("name", e.target.value)} /></label>
        <label>Comuna<select value={draft.commune} onChange={e => edit("commune", e.target.value)}>{lookups.communes.map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Sector del circuito<select required={draft.location_verified} value={draft.sector ?? ""} onChange={e => edit("sector", e.target.value)}><option value="">Fuera del circuito / por revisar</option>{sectors.map(s => <option key={s}>{s}</option>)}</select></label>
        <label><span id="location-source-label">Fuente de ubicación</span><input required={draft.location_verified} minLength={draft.location_verified ? 5 : undefined} maxLength={1000} aria-labelledby="location-source-label" aria-describedby="location-source-help" value={draft.location_source ?? ""} onChange={e => edit("location_source", e.target.value)} /><small id="location-source-help">Indica cómo se confirmó el punto, por ejemplo: «Confirmado por el dueño». Al verificar la ubicación, se requieren sector, ambas coordenadas y una fuente de al menos 5 caracteres.</small></label>
        <label><span><input type="checkbox" checked={draft.location_verified ?? false} onChange={e => edit("location_verified", e.target.checked)} /> Ubicación verificada para el mapa</span></label>
        <label>Rubro<select value={draft.category} onChange={e => edit("category", e.target.value)}>{lookups.categories.map(v => <option key={v}>{v}</option>)}</select></label>
        <label className="wide">Resumen<input required minLength={5} maxLength={400} value={draft.summary} onChange={e => edit("summary", e.target.value)} /></label>
        <label className="wide">Descripción<textarea required minLength={5} maxLength={4000} rows={4} value={draft.description} onChange={e => edit("description", e.target.value)} /></label>
        <label className="wide">Servicios o productos (uno por línea)<textarea required rows={3} value={draft.offerings.join("\n")} onChange={e => edit("offerings", e.target.value.split("\n"))} /></label>
        <label className="wide">Dirección o referencia rural<input required minLength={2} maxLength={255} value={draft.area} onChange={e => edit("area", e.target.value)} /></label>
        <AdminLocationPicker key={draft.id ?? "new"} latitude={draft.latitude} longitude={draft.longitude} disabled={busy} onChange={locate} />
        <label>Latitud<input required={draft.location_verified || draft.longitude !== null || (!draft.demo && draft.status === "Aprobado")} type="number" step="any" min={-90} max={90} value={draft.latitude ?? ""} onChange={e => edit("latitude", e.target.value === "" ? null : Number(e.target.value))} /></label>
        <label>Longitud<input required={draft.location_verified || draft.latitude !== null} type="number" step="any" min={-180} max={180} value={draft.longitude ?? ""} onChange={e => edit("longitude", e.target.value === "" ? null : Number(e.target.value))} /></label>
        <label>WhatsApp<input required={!draft.demo && draft.status === "Aprobado"} placeholder="+56912345678" pattern="\+[1-9][0-9]{7,14}" value={draft.whatsapp} onChange={e => edit("whatsapp", e.target.value)} /></label>
        <label>Horario<input required minLength={2} maxLength={255} value={draft.hours} onChange={e => edit("hours", e.target.value)} /></label>
        <label className="wide">Palabras clave<input maxLength={1000} value={draft.keywords} onChange={e => edit("keywords", e.target.value)} /></label>
      </div></fieldset>
      <fieldset disabled={busy}><legend>Moderación y antecedentes privados</legend><div className="admin-fields">
        <label>Razón social<input maxLength={150} value={draft.legal_name} onChange={e => edit("legal_name", e.target.value)} /></label><label>RUT<input maxLength={12} value={draft.tax_id} onChange={e => edit("tax_id", e.target.value)} /></label>
        <label>Estado<select value={draft.status} onChange={e => edit("status", e.target.value)}><option>Pendiente</option>{user.role === "Administrador" && <option>Aprobado</option>}<option>Suspendido</option></select></label>
        <label>Icono de referencia<select value={draft.visual} onChange={e => edit("visual", e.target.value)}>{Object.entries({ stay: "Alojamiento", food: "Comida", craft: "Artesanía", outdoors: "Naturaleza", coffee: "Café", shop: "Comercio", camp: "Camping", textile: "Tejidos" }).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
        <label className="admin-check"><input type="checkbox" checked={draft.featured} onChange={e => edit("featured", e.target.checked)} />Destacar ficha</label><label className="admin-check"><input type="checkbox" checked={draft.demo} onChange={e => edit("demo", e.target.checked)} />Datos ficticios de demostración</label>
      </div><p className="admin-hint">Una ficha real requiere ubicación y contacto verificados para ser aprobada. Los operadores territoriales guardan sus cambios como pendientes de revisión.</p></fieldset></form>
      <section className="admin-photos"><h3>Fotografías</h3><p>Hasta 8 imágenes. Se optimizan a WebP y se eliminan los metadatos de origen.</p>
        {!draft.id ? <p>Guarda la ficha antes de añadir fotografías.</p> : <label className="admin-upload">Añadir fotografía<input disabled={busy} type="file" accept="image/jpeg,image/png,image/webp" onChange={e => {
          const file = e.target.files?.[0]; if (!file) return; const body = new FormData(); body.append("file", file); e.target.value = "";
          run(async () => { const result = await api<Business>(`/businesses/${draft.id}/photos`, { method: "POST", body }); setDraft(result); setRows(await api<Business[]>("/businesses")); setNotice("Imagen añadida."); });
        }} /></label>}
        <div className="admin-photo-grid">{draft.photos.map(photo => <article key={photo.id}><img src={photo.url} alt={photo.alt} /><label>Texto alternativo<input maxLength={150} value={photo.alt} onChange={e => edit("photos", draft.photos.map(p => p.id === photo.id ? { ...p, alt: e.target.value } : p))} /></label><label>Orden<input type="number" min={0} max={100} value={photo.order} onChange={e => edit("photos", draft.photos.map(p => p.id === photo.id ? { ...p, order: Number(e.target.value) } : p))} /></label><label className="admin-check"><input type="checkbox" checked={photo.cover} onChange={e => edit("photos", draft.photos.map(p => p.id === photo.id ? { ...p, cover: e.target.checked } : p))} />Portada</label><div><button disabled={busy} onClick={() => updatePhoto(photo)}>Guardar imagen</button><button disabled={busy} onClick={() => updatePhoto(photo, true)}>Eliminar</button></div></article>)}</div>
      </section></> }</section></div>}
    {tab === "metrics" && <section className="admin-report"><span className="admin-eyebrow">ÚLTIMOS 90 DÍAS</span><h1>Uso anónimo del tótem</h1><p>Se registran tipos de interacción y tiempos de respuesta. Las consultas y los datos personales de visitantes no se almacenan. Un QR mostrado no confirma que haya sido escaneado.</p><table><thead><tr><th>Interacción</th><th>Cantidad</th><th>Tiempo medio</th></tr></thead><tbody>{metrics.map(m => <tr key={m.event}><td>{m.event}</td><td>{m.count}</td><td>{m.average_ms === null ? "—" : `${m.average_ms} ms`}</td></tr>)}</tbody></table>{!metrics.length && <p>Aún no hay interacciones registradas.</p>}</section>}
    {tab === "audit" && <section className="admin-report"><h1>Registro de auditoría</h1><p>Últimas 200 operaciones. Los cambios incluyen una copia de los datos anteriores y posteriores.</p>{logs.map(log => <details key={log.id}><summary><strong>{log.action}</strong> · Usuario {log.user_id} · {new Date(log.at + (log.at.endsWith("Z") ? "" : "Z")).toLocaleString("es-CL")}</summary><pre>{JSON.stringify(log.detail, null, 2)}</pre></details>)}</section>}
    {tab === "users" && <section className="admin-report"><div className="admin-editor-heading"><h1>Equipo autorizado</h1><button onClick={() => setUserDraft({ ...blankUser })}>+ Nuevo usuario</button></div><table><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{users.map(u => <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.active ? "Activo" : "Inactivo"}</td><td><button onClick={() => setUserDraft({ ...u, password: "" })}>Editar</button></td></tr>)}</tbody></table>
      {userDraft && <form className="admin-user-form" onSubmit={e => { e.preventDefault(); run(async () => { await api(userDraft.id ? `/users/${userDraft.id}` : "/users", { method: userDraft.id ? "PUT" : "POST", body: JSON.stringify(userDraft) }); setUsers(await api<User[]>("/users")); setUserDraft(null); setNotice("Usuario guardado."); }); }}><h2>{userDraft.id ? "Editar usuario" : "Nuevo usuario"}</h2><div className="admin-fields"><label>Nombre<input required value={userDraft.name} onChange={e => setUserDraft({ ...userDraft, name: e.target.value })} /></label><label>Correo<input required type="email" value={userDraft.email} onChange={e => setUserDraft({ ...userDraft, email: e.target.value })} /></label><label>Rol<select value={userDraft.role} onChange={e => setUserDraft({ ...userDraft, role: e.target.value })}><option>Operador Territorial</option><option>Administrador</option></select></label><label>{userDraft.id ? "Nueva contraseña (opcional)" : "Contraseña"}<input type="password" required={!userDraft.id} minLength={12} autoComplete="new-password" value={userDraft.password} onChange={e => setUserDraft({ ...userDraft, password: e.target.value })} /></label><label className="admin-check"><input type="checkbox" checked={userDraft.active} onChange={e => setUserDraft({ ...userDraft, active: e.target.checked })} />Usuario activo</label></div><button className="admin-primary" disabled={busy}>Guardar usuario</button><button type="button" onClick={() => setUserDraft(null)}>Cancelar</button></form>}
    </section>}
  </main>;
}
