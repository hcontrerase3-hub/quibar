import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type Props = {
  latitude: number | null;
  longitude: number | null;
  disabled: boolean;
  onChange: (latitude: number, longitude: number) => void;
};
type MapInfo = { available: boolean; bounds: [number, number, number, number]; minZoom: number; maxZoom: number; attribution: string };

function validPoint(latitude: number | null, longitude: number | null): latitude is number {
  return latitude !== null && longitude !== null && Number.isFinite(latitude) && Number.isFinite(longitude)
    && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180;
}

export default function AdminLocationPicker(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.Marker | null>(null);
  const bounds = useRef<L.LatLngBounds | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("Cargando mapa local…");

  function select(point: L.LatLng) {
    if (latest.current.disabled) return;
    const wrapped = point.wrap();
    if (validPoint(wrapped.lat, wrapped.lng)) latest.current.onChange(wrapped.lat, wrapped.lng);
  }

  useEffect(() => {
    const controller = new AbortController();
    let observer: ResizeObserver | undefined;
    fetch("/api/quibar/map", { signal: controller.signal, cache: "no-store" }).then(async response => {
      if (!response.ok) throw Error();
      const info: MapInfo = await response.json();
      if (controller.signal.aborted) return;
      if (!info.available) {
        setMessage("El mapa local no está instalado. Puedes introducir las coordenadas manualmente.");
        return;
      }
      if (!container.current) return;
      const current = L.map(container.current, { minZoom: info.minZoom, maxZoom: info.maxZoom, scrollWheelZoom: false });
      map.current = current;
      bounds.current = L.latLngBounds([[info.bounds[1], info.bounds[0]], [info.bounds[3], info.bounds[2]]]);
      current.fitBounds(bounds.current, { padding: [20, 20] });
      L.tileLayer("/tiles/{z}/{x}/{y}", { minZoom: info.minZoom, maxZoom: info.maxZoom, attribution: info.attribution })
        .on("tileerror", () => setMessage("No se pudo mostrar este sector o nivel del mapa. Prueba alejando el mapa o introduce las coordenadas manualmente."))
        .addTo(current);
      current.on("click", (event: L.LeafletMouseEvent) => select(event.latlng));
      observer = new ResizeObserver(() => {
        current.invalidateSize({ pan: false });
        if (!marker.current && bounds.current) current.fitBounds(bounds.current, { padding: [20, 20] });
      });
      observer.observe(container.current);
      setMessage("");
      setReady(true);
    }).catch(() => {
      if (!controller.signal.aborted) setMessage("No pudimos cargar el mapa local. Puedes introducir las coordenadas manualmente.");
    });
    return () => {
      controller.abort();
      observer?.disconnect();
      map.current?.remove();
      map.current = null;
      marker.current = null;
    };
  }, []);

  useEffect(() => {
    const current = map.current;
    if (!ready || !current) return;
    if (!validPoint(props.latitude, props.longitude)) {
      marker.current?.remove();
      marker.current = null;
      if (bounds.current) current.fitBounds(bounds.current, { padding: [20, 20] });
      return;
    }
    const point: L.LatLngTuple = [props.latitude, props.longitude!];
    if (!marker.current) {
      const icon = L.divIcon({ className: "admin-location-marker", html: "<span></span>", iconSize: [28, 28], iconAnchor: [14, 14] });
      const pin = L.marker(point, { icon, draggable: !props.disabled, title: "Ubicación de la tienda. Arrastra para ajustar." }).addTo(current);
      pin.on("dragend", () => {
        if (latest.current.disabled) {
          const { latitude, longitude } = latest.current;
          if (validPoint(latitude, longitude)) pin.setLatLng([latitude, longitude!]);
        } else select(pin.getLatLng());
      });
      marker.current = pin;
      current.setView(point, Math.min(15, current.getMaxZoom()));
    } else {
      marker.current.setLatLng(point);
      current.panTo(point);
    }
    if (props.disabled) marker.current.dragging?.disable();
    else marker.current.dragging?.enable();
  }, [ready, props.latitude, props.longitude, props.disabled]);

  return <div className="admin-location-picker wide">
    <p><strong>Ubicación en el mapa</strong></p>
    <p id="admin-location-help">Pulsa el mapa para ubicar la tienda y arrastra el marcador para ajustar el punto. Las coordenadas se completan automáticamente; guarda la ficha para conservar el cambio.</p>
    <div ref={container} className="admin-location-map" role="region" aria-label="Elegir ubicación de la tienda" aria-describedby="admin-location-help" hidden={!ready} />
    {ready && <button type="button" disabled={props.disabled} onClick={() => { if (map.current) select(map.current.getCenter()); }}>Usar centro del mapa</button>}
    {message && <p role="status">{message}</p>}
  </div>;
}
