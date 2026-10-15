"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, BedDouble, Compass, Delete, MapPin, RotateCcw, Search, ShoppingBag, Sparkles, UtensilsCrossed, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { asBusiness, businesses, categories, categoryIcons, normalize, recommend } from "./data";
import type { Business, Category } from "./data";

const prompts = [
  { label: "Quiero comer", query: "Quiero comer algo rico", icon: UtensilsCrossed },
  { label: "Busco alojamiento", query: "Busco dónde alojarme", icon: BedDouble },
  { label: "Salir a pasear", query: "Ideas para pasear", icon: Compass },
  { label: "Comprar un regalo", query: "Un regalo hecho a mano", icon: ShoppingBag },
];

type GuideMessage = {
  role: "user" | "assistant"; text: string; matches: Business[];
  mode?: "ia_local" | "basico"; elapsedMs?: number;
};

export default function Home() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<Category | "Todos">("Todos");
  const [commune, setCommune] = useState("Todas");
  const [selected, setSelected] = useState<Business | null>(null);
  const [welcome, setWelcome] = useState(true);
  const [guideInput, setGuideInput] = useState("");
  const [messages, setMessages] = useState<GuideMessage[]>([]);
  const [guideLoading, setGuideLoading] = useState(false);
  const [catalog, setCatalog] = useState<Business[]>([]);
  const [catalogReady, setCatalogReady] = useState(false);
  const [keyboardTarget, setKeyboardTarget] = useState<"catalog" | "guide" | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const visible = useMemo(() => catalog.filter(b => {
    const words = normalize(b.name + " " + b.summary + " " + b.category + " " + b.commune + " " + b.offerings.join(" ") + " " + b.keywords);
    return (category === "Todos" || b.category === category) && (commune === "Todas" || b.commune === commune) && (!search.trim() || words.includes(normalize(search.trim())));
  }), [catalog, category, commune, search]);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/quibar/catalog", { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error("Catálogo local no disponible"); return response.json(); })
      .then((rows: Omit<Business, "icon">[]) => {
        if (Array.isArray(rows)) setCatalog(rows.filter(row => row.status === "Aprobado").map(asBusiness));
      }).catch(() => { if (!controller.signal.aborted) setCatalog(businesses); })
      .finally(() => { if (!controller.signal.aborted) setCatalogReady(true); });
    return () => controller.abort();
  }, []);

  const resetSession = useCallback(() => {
    requestRef.current?.abort();
    requestRef.current = null;
    setSearch(""); setCategory("Todos"); setCommune("Todas");
    setSelected(null); setGuideInput(""); setMessages([]); setGuideLoading(false); setKeyboardTarget(null);
    setWelcome(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const restart = () => { clearTimeout(timer); timer = setTimeout(resetSession, 60000); };
    for (const name of ["pointerdown", "keydown", "input", "touchstart"]) window.addEventListener(name, restart);
    restart();
    return () => {
      clearTimeout(timer);
      for (const name of ["pointerdown", "keydown", "input", "touchstart"]) window.removeEventListener(name, restart);
    };
  }, [resetSession]);

  async function askQuibar(value: string) {
    const query = value.trim();
    if (!query || guideLoading || !catalogReady) return;
    const previous = messages.slice(-6);
    const contextIds = [...previous].reverse().find(message => message.role === "assistant")?.matches.map(b => b.id) ?? [];
    setMessages(current => [...current, { role: "user", text: query, matches: [] }]);
    setGuideInput(""); setKeyboardTarget(null); setGuideLoading(true);
    const controller = new AbortController();
    requestRef.current = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, 120000);
    try {
      const response = await fetch("/api/quibar/chat", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ query, context_ids: contextIds,
          history: previous.map(message => ({ role: message.role, content: message.text.slice(0, 300) })) }),
      });
      if (!response.ok) throw new Error("Motor local no disponible");
      const result: { reply: string; matches: { id: string }[]; mode: "ia_local" | "basico"; elapsed_ms: number } = await response.json();
      if (requestRef.current !== controller) return;
      const matches = result.matches.map(match => catalog.find(b => b.id === match.id)).filter((b): b is Business => !!b);
      setMessages(current => [...current, { role: "assistant", text: result.reply, matches,
        mode: result.mode, elapsedMs: result.elapsed_ms }]);
    } catch {
      if (requestRef.current !== controller) return;
      if (controller.signal.aborted && !timedOut) return;
      const fallback = recommend(query, catalog);
      setMessages(current => [...current, { role: "assistant", text: fallback.response,
        matches: fallback.matches, mode: "basico" }]);
    } finally {
      window.clearTimeout(timeout);
      if (requestRef.current === controller) requestRef.current = null;
      if (!controller.signal.aborted || timedOut) setGuideLoading(false);
    }
  }
  function startExplore(guideFirst = false) {
    setWelcome(false);
    if (guideFirst) {
      setKeyboardTarget("guide");
      window.setTimeout(() => document.getElementById("quibar-query")?.focus(), 0);
    }
  }
  function typeKey(key: string) {
    const setter = keyboardTarget === "guide" ? setGuideInput : setSearch;
    setter(value => key === "Borrar" ? value.slice(0, -1) : value + (key === "Espacio" ? " " : key.toLocaleLowerCase("es")));
  }

  return (
    <main className="kiosk-shell">
      {welcome && <div className="kiosk-welcome" onClick={() => startExplore()} role="presentation">
        <div className="kiosk-welcome-inner">
          <span className="kiosk-welcome-tag">GUÍA COMERCIAL INTERACTIVA · PROTOTIPO ACADÉMICO</span>
          <img src="/quibar-angostura-original.png" alt="Quíbar, mascota creada por niños y niñas de Angostura del Biobío" />
          <h1>Hola, soy <em>Quibar.</em></h1>
          <p>Descubre emprendimientos y panoramas de Quilaco y Santa Bárbara.</p>
          <div className="kiosk-welcome-actions">
            <button type="button" onClick={e => {e.stopPropagation();startExplore()}}><Search size={29}/> Explorar comercios <ArrowRight size={25}/></button>
            <button type="button" onClick={e => {e.stopPropagation();startExplore(true)}}><Sparkles size={29}/> Pregúntale a Quibar <ArrowRight size={25}/></button>
          </div>
          <span className="kiosk-welcome-foot">Toca una opción para comenzar · Datos de negocios ficticios</span>
        </div>
      </div>}
      <header className="kiosk-header" inert={welcome}>
        <div className="kiosk-header-inner">
          <div className="kiosk-brand"><span className="kiosk-brand-mark"><Compass size={28}/></span><span>quibar<span className="brand-period">.</span></span><span className="kiosk-header-divider"/><span className="kiosk-region">Quilaco · Santa Bárbara</span></div>
          <span className="kiosk-demo-tag">DEMOSTRACIÓN ACADÉMICA</span>
          <button type="button" className="kiosk-home" onClick={resetSession}><RotateCcw size={22}/> Volver al inicio</button>
        </div>
      </header>

      <div className="kiosk-layout" inert={welcome}>
        <aside className="kiosk-guide" aria-label="Quibar, guía interactiva">
          <div className="kiosk-guide-top">
            <img src="/quibar-angostura-original.png" alt="Quíbar, mascota creada por niños y niñas de Angostura del Biobío" />
            <div className="kiosk-guide-intro"><span className="kiosk-eyebrow">TU GUÍA LOCAL</span><h1>¡Hola! Soy <em>Quibar.</em></h1><p>¿Qué te gustaría descubrir hoy?</p></div>
          </div>
          <div className="kiosk-guide-content kiosk-chat">
            {!messages.length && <div className="kiosk-prompt-grid">{prompts.map(p => <button key={p.label} type="button" disabled={guideLoading || !catalogReady} onClick={() => void askQuibar(p.query)}><p.icon size={26}/><span>{p.label}</span><ArrowRight size={20}/></button>)}</div>}
            {!!messages.length && <div className="kiosk-chat-thread" role="log" aria-live="polite" aria-label="Conversación con Quíbar">
              {messages.map((message, index) => <div className={"kiosk-chat-message " + message.role} key={index}>
                <span className="kiosk-chat-label">{message.role === "user" ? "TÚ" : message.mode === "ia_local" ? "QUÍBAR · IA LOCAL" : "QUÍBAR · MODO BÁSICO"}</span>
                <p>{message.text}</p>
                {message.matches.map(b => <button type="button" className="kiosk-recommendation" key={b.id} onClick={() => setSelected(b)}><span><strong>{b.name}</strong><small>{b.category} · {b.commune}</small></span><ArrowRight size={23}/></button>)}
              </div>)}
              {guideLoading && <p className="kiosk-chat-pending">Quíbar está buscando en el catálogo local…</p>}
            </div>}
            <p className="kiosk-or">{messages.length ? "Puedes seguir preguntando" : "O escríbeme lo que buscas"}</p>
            <form className="kiosk-guide-form" onSubmit={e => {e.preventDefault();void askQuibar(guideInput)}}>
              <label htmlFor="quibar-query" className="sr-only">Pregúntale a Quíbar</label>
              <Input id="quibar-query" inputMode="none" maxLength={250} value={guideInput} onFocus={() => setKeyboardTarget("guide")} onChange={e => setGuideInput(e.target.value)} placeholder="Ej: un café en Quilaco"/>
              <button type="submit" aria-label="Preguntar a Quíbar" disabled={!guideInput.trim() || guideLoading || !catalogReady}><ArrowRight size={23}/></button>
            </form>
            {!!messages.length && <button type="button" className="kiosk-ask-again" onClick={() => {requestRef.current?.abort();requestRef.current = null;setMessages([]);setGuideLoading(false);setKeyboardTarget(null)}}><ArrowLeft size={20}/> Nueva conversación</button>}
          </div>
          <p className="kiosk-guide-note">Quíbar usa solo fichas aprobadas de ejemplo. Si la IA local no está disponible, el catálogo sigue funcionando.</p>
        </aside>

        <section className="kiosk-catalog" aria-label="Catálogo de emprendimientos">
          <div className="kiosk-catalog-header"><div><span className="kiosk-eyebrow">EXPLORA EL TERRITORIO</span><h2>Encuentra tu próximo panorama</h2></div><span className="kiosk-count" aria-live="polite">{visible.length} {visible.length === 1 ? "opción" : "opciones"}</span></div>
          <div className="kiosk-search-row">
            <label className="kiosk-search"><Search size={27}/><span className="sr-only">Buscar negocios o actividades</span><Input aria-label="Buscar negocios o actividades" inputMode="none" value={search} onFocus={() => setKeyboardTarget("catalog")} onChange={e => setSearch(e.target.value)} placeholder="Buscar comida, cabañas, regalos…"/>{search && <button type="button" aria-label="Borrar búsqueda" onClick={() => setSearch("")}><X size={23}/></button>}</label>
            <Select value={commune} onValueChange={value => {setCommune(value);setKeyboardTarget(null)}}><SelectTrigger className="kiosk-commune" aria-label="Filtrar por comuna"><MapPin size={23}/><SelectValue placeholder="Todas las comunas"/></SelectTrigger><SelectContent><SelectItem className="kiosk-option" value="Todas">Todas las comunas</SelectItem><SelectItem className="kiosk-option" value="Quilaco">Quilaco</SelectItem><SelectItem className="kiosk-option" value="Santa Bárbara">Santa Bárbara</SelectItem></SelectContent></Select>
          </div>
          <div className="kiosk-categories" role="group" aria-label="Filtrar por categoría">{categories.map(c => {
            const Icon = c === "Todos" ? Sparkles : categoryIcons[c];
            return <button key={c} type="button" className={category === c ? "active" : ""} aria-pressed={category === c} onClick={() => {setCategory(c);setKeyboardTarget(null)}}><Icon size={24}/>{c}</button>;
          })}</div>
          {!catalogReady ? <div className="kiosk-empty"><p>Cargando el catálogo local…</p></div> : visible.length ? <div className="kiosk-grid">{visible.map(b => <BusinessCard key={b.id} business={b} onOpen={() => {setSelected(b);setKeyboardTarget(null)}}/>)}</div> : <div className="kiosk-empty"><Search size={42}/><h3>No encontramos opciones con esos filtros</h3><p>Prueba otra búsqueda o vuelve a ver todo el catálogo.</p><button type="button" onClick={() => {setSearch("");setCategory("Todos");setCommune("Todas");setKeyboardTarget(null)}}>Ver todas las opciones <ArrowRight size={20}/></button></div>}
          <p className="kiosk-catalog-note">Nombres, servicios y horarios ficticios. Este prototipo no permite reservas ni contacto con negocios reales. Tras 60 segundos sin uso vuelve al inicio.</p>
        </section>
      </div>

      {keyboardTarget && !selected && <TouchKeyboard target={keyboardTarget} onKey={typeKey} onClose={() => setKeyboardTarget(null)} onSubmit={() => {if (keyboardTarget === "guide") askQuibar(guideInput); else setKeyboardTarget(null)}}/>}

      <Dialog open={!!selected} onOpenChange={open => {if (!open) setSelected(null)}}>
        <DialogContent className="kiosk-detail" showCloseButton={false} aria-describedby="business-description">{selected && <>
          <div className={"detail-visual visual-" + selected.visual}><selected.icon size={85} strokeWidth={1.15}/><span>IMAGEN REFERENCIAL · DEMOSTRACIÓN</span></div>
          <button type="button" className="kiosk-detail-close" onClick={() => setSelected(null)} aria-label="Cerrar ficha"><X size={27}/> Cerrar</button>
          <DialogHeader><span className="detail-meta"><MapPin size={20}/>{selected.area} · {selected.commune} · {selected.category}</span><DialogTitle>{selected.name}</DialogTitle><DialogDescription id="business-description">{selected.description}</DialogDescription></DialogHeader>
          <div className="detail-section"><h3>¿Qué ofrece?</h3><div className="offering-list">{selected.offerings.map(item => <span key={item}>{item}</span>)}</div></div>
          <div className="detail-hours"><strong>Horario de ejemplo</strong><span>{selected.hours}</span></div>
          <p className="detail-note">Ficha ficticia para presentar Quibar. No corresponde a un negocio real.</p>
        </>}</DialogContent>
      </Dialog>
    </main>
  );
}

function BusinessCard({ business: b, onOpen }: { business: Business; onOpen: () => void }) {
  const Icon = b.icon;
  return <article className="business-card"><button className="card-click" type="button" onClick={onOpen} aria-label={"Ver ficha de " + b.name}><div className={"card-visual visual-" + b.visual}><Icon size={70} strokeWidth={1.25} aria-hidden="true"/><span className="image-label">IMAGEN REFERENCIAL</span><span className="category-badge">{b.category}</span></div><div className="card-copy"><span className="card-location"><MapPin size={19}/>{b.commune}</span><h3>{b.name}</h3><p>{b.summary}</p><span className="card-link">Ver ficha <ArrowRight size={22}/></span></div></button></article>;
}

function TouchKeyboard({ target, onKey, onClose, onSubmit }: { target: "catalog" | "guide"; onKey: (key: string) => void; onClose: () => void; onSubmit: () => void }) {
  return <div className="touch-keyboard" role="group" aria-label="Teclado táctil">
    <div className="touch-keyboard-heading"><span>ESCRIBIENDO EN: {target === "guide" ? "PREGÚNTALE A QUIBAR" : "BUSCAR EN EL CATÁLOGO"}</span><button type="button" onClick={onClose}><X size={22}/> Cerrar teclado</button></div>
    {["qwertyuiop", "asdfghjklñ", "zxcvbnm"].map(row => <div className="touch-keyboard-row" key={row}>{Array.from(row).map(key => <button type="button" key={key} onClick={() => onKey(key)}>{key.toLocaleUpperCase("es")}</button>)}</div>)}
    <div className="touch-keyboard-row touch-keyboard-actions"><button type="button" onClick={() => onKey("Borrar")}><Delete size={22}/> Borrar</button><button type="button" onClick={() => onKey("Espacio")}>Espacio</button><button type="button" className="keyboard-done" onClick={onSubmit}>{target === "guide" ? "Preguntar" : "Ver resultados"} <ArrowRight size={23}/></button></div>
  </div>;
}
