import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { QRCodeSVG } from "qrcode.react";
import { MapPin, QrCode, X } from "lucide-react";
import type { Business } from "./data";
import { track } from "../lib/metrics";
import "leaflet/dist/leaflet.css";
import "./business-detail.css";

export function PhotoGallery({ business }: { business: Business }) {
  const [active, setActive] = useState<number | null>(null);
  useEffect(() => setActive(null), [business.id]);
  const photos = business.photos ?? [];
  const current = photos.find(photo => photo.id === active) ?? photos.find(photo => photo.cover) ?? photos[0];
  return current ? <div className="business-gallery"><img className="business-gallery-main" src={current.url} alt={current.alt} />{photos.length > 1 && <div className="business-gallery-thumbs">{photos.map(photo => <button aria-label={`Ver ${photo.alt || "fotografía"}`} aria-pressed={current.id === photo.id} key={photo.id} onClick={() => setActive(photo.id)}><img src={photo.url} alt="" /></button>)}</div>}</div> : <div className={`detail-visual visual-${business.visual}`}><business.icon size={85} strokeWidth={1.15} /><span>IMAGEN REFERENCIAL{business.demo ? " · DEMOSTRACIÓN" : ""}</span></div>;
}

type MapInfo = { available: boolean; minZoom?: number; maxZoom?: number; attribution?: string };
function LocalMap({ latitude, longitude }: { latitude: number; longitude: number }) {
  const container = useRef<HTMLDivElement>(null);
  const [message, setMessage] = useState("Cargando mapa local…");
  useEffect(() => {
    if (!container.current) return;
    const controller = new AbortController();
    const map = L.map(container.current, { scrollWheelZoom: false, zoomControl: true, minZoom: 0, maxZoom: 19 }).setView([latitude, longitude], 13);
    L.circleMarker([latitude, longitude], { radius: 11, color: "#fff", weight: 3, fillColor: "#0b6661", fillOpacity: 1 }).addTo(map);
    fetch("/api/quibar/map", { signal: controller.signal }).then(response => {
      if (!response.ok) throw new Error();
      return response.json() as Promise<MapInfo>;
    }).then(info => {
      if (!info.available) { setMessage("La ubicación está disponible. Aún no hay un mapa local instalado."); return; }
      map.setMinZoom(info.minZoom ?? 0); map.setMaxZoom(info.maxZoom ?? 16);
      L.tileLayer("/tiles/{z}/{x}/{y}", { minZoom: info.minZoom, maxZoom: info.maxZoom, attribution: info.attribution })
        .on("tileerror", () => setMessage("Esta zona o nivel de detalle no está incluido en el mapa local."))
        .addTo(map);
      setMessage("Mapa local · Puedes ampliar con los botones o con dos dedos.");
    }).catch(() => { if (!controller.signal.aborted) setMessage("El mapa local no está disponible. Puedes llevar las coordenadas a tu celular."); });
    const timer = window.setTimeout(() => map.invalidateSize(), 100);
    return () => { controller.abort(); clearTimeout(timer); map.remove(); };
  }, [latitude, longitude]);
  return <><div ref={container} className="business-map" role="region" aria-label="Mapa de ubicación del comercio" /><p className="map-status" role="status">{message}</p></>;
}

export function BusinessLocation({ business }: { business: Business }) {
  const [showQr, setShowQr] = useState(false);
  useEffect(() => setShowQr(false), [business.id]);
  const hasLocation = business.latitude != null && business.longitude != null;
  const route = hasLocation ? `https://www.google.com/maps/dir/?api=1&destination=${business.latitude},${business.longitude}` : null;
  const contact = business.whatsapp ? `https://wa.me/${business.whatsapp.replace(/\D/g, "")}` : null;
  return <section className="business-location"><div className="business-location-heading"><h3><MapPin size={21} /> Ubicación y contacto</h3>{(route || contact) && <button className="take-to-phone" onClick={() => { setShowQr(value => !value); if (!showQr) track("QR_MOSTRADO", business.id); }}>{showQr ? <X size={21} /> : <QrCode size={21} />}{showQr ? "Cerrar códigos" : "Llevar a mi celular"}</button>}</div>
    {hasLocation ? <><LocalMap latitude={business.latitude!} longitude={business.longitude!} /><p className="business-coordinates">{business.latitude!.toFixed(5)}, {business.longitude!.toFixed(5)}{business.demo ? " · Posición de ejemplo" : ""}</p></> : <p className="map-status">Esta ficha aún no tiene coordenadas verificadas.</p>}
    {business.whatsapp && <p className="business-contact">Contacto: {business.whatsapp}</p>}
    {showQr && <div className="business-qr-panel" aria-label="Códigos para llevar al celular"><p>Escanea un código con la cámara de tu celular.</p><div className="business-qr-grid">{[[route, "Abrir ruta en mapas"], [contact, "Contactar por WhatsApp"]].map(([url, title]) => url && <figure key={title}><QRCodeSVG value={url} size={220} level="M" marginSize={4} title={title ?? undefined} /><figcaption>{title}</figcaption></figure>)}</div><p className="qr-note">El tótem genera estos códigos sin internet. Para usar mapas o WhatsApp, tu celular puede necesitar conexión o mapas descargados.</p></div>}
  </section>;
}
