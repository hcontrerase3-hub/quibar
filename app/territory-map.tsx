import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Catalog, Place, Route } from './map-types';
type Props = { catalog: Catalog; places: Place[]; selected: string | null; route: Route | null; suggested: string[]; resetKey: number; onSelect: (place: Place) => void };
export default function TerritoryMap({catalog, places, selected, route, suggested, resetKey, onSelect}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const routeLayer = useRef<L.GeoJSON | null>(null);
  const select = useRef(onSelect); select.current = onSelect;
  const [revision, setRevision] = useState(0);
  const [message, setMessage] = useState('Cargando mapa del circuito…');
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    if (!container.current) return;
    const controller = new AbortController();
    const current = L.map(container.current, {zoomControl:false, attributionControl:true, scrollWheelZoom:true});
    map.current = current; layer.current = L.layerGroup().addTo(current);
    L.control.zoom({position:'bottomleft'}).addTo(current);
    current.fitBounds([[catalog.bounds[1],catalog.bounds[0]],[catalog.bounds[3],catalog.bounds[2]]],{padding:[28,28]});
    const change = () => setRevision(n=>n+1); current.on('zoomend moveend',change);
    fetch('/api/quibar/map',{signal:controller.signal,cache:'no-store'}).then(async response => {
      if (!response.ok) throw Error(); const info = await response.json();
      if (!info.available) { setMessage('El mapa local aún no está instalado. Puedes consultar los lugares de la lista.'); return; }
      setAvailable(true);setMessage('');current.setMinZoom(info.minZoom);current.setMaxZoom(info.maxZoom);
      L.tileLayer('/tiles/{z}/{x}/{y}',{minZoom:info.minZoom,maxZoom:info.maxZoom,attribution:info.attribution}).on('tileerror',()=>setMessage('Este nivel o sector no está incluido en el mapa local. Prueba alejando el mapa.')).addTo(current);
    }).catch(()=>{if(!controller.signal.aborted)setMessage('No pudimos cargar el mapa local. La lista de lugares sigue disponible.');});
    const observer = new ResizeObserver(()=>{current.invalidateSize({pan:false});if(routeLayer.current)current.fitBounds(routeLayer.current.getBounds(),{padding:[55,55],maxZoom:16});}); observer.observe(container.current);
    return ()=>{controller.abort();observer.disconnect();current.remove();map.current=null;layer.current=null;};
  }, []);
  useEffect(() => {
    const current=map.current, markers=layer.current;if(!current||!markers)return;
    markers.clearLayers();
    const pinned = new Set([selected, ...suggested,...(route?.stops.map(p=>p.key)??[]), route?.destination.key]);
    const groups: {point:L.Point; items:Place[]}[]=[];
    for(const place of places.filter(p=>p.located&&p.latitude!=null&&p.longitude!=null)){
      const point=current.project([place.latitude!,place.longitude!]);
      const group=!pinned.has(place.key)?groups.find(g=>!g.items.some(p=>pinned.has(p.key))&&g.point.distanceTo(point)<42):undefined;
      if(group)group.items.push(place);else groups.push({point,items:[place]});
    }
    for(const group of groups){
      const first=group.items[0]; const count=group.items.length;
      const stop=route?.stops.findIndex(p=>p.key===first.key)??-1;
      const destination=route?.destination.key===first.key;
      const label=count>1?String(count):destination?'D':stop>=0?String(stop+1):first.kind==='business'?'●':'◆';
      const icon=L.divIcon({className:'place-marker-wrap',html:`<span class="place-marker ${count>1?'cluster':first.kind} ${first.key===selected?'selected':''} ${suggested.includes(first.key)?'suggested':''} ${destination||stop>=0?'on-route':''}">${label}</span>`,iconSize:[44,48],iconAnchor:[22,43]});
      const marker=L.marker([first.latitude!,first.longitude!],{icon,title:count>1?`${count} lugares. Toca para acercar`:first.name,keyboard:true}).addTo(markers);
      const tooltip=document.createElement('span');tooltip.textContent=count>1?`${count} lugares`:first.name;marker.bindTooltip(tooltip,{direction:'top',offset:[0,-30]});
      marker.on('click',()=>{if(count>1){current.fitBounds(L.latLngBounds(group.items.map(p=>[p.latitude!,p.longitude!])),{padding:[60,60],maxZoom:Math.min(current.getZoom()+3,current.getMaxZoom())});}else select.current(first);});
    }
    if(catalog.station.configured){const icon=L.divIcon({className:'station-marker',html:'<span></span>',iconSize:[24,24]});L.marker([catalog.station.latitude!,catalog.station.longitude!],{icon,title:'Estás aquí: '+catalog.station.name}).addTo(markers).bindTooltip('Estás aquí');}
  },[places,selected,suggested,route,catalog.station,revision]);
  useEffect(()=>{const current=map.current;if(!current)return;routeLayer.current?.remove();routeLayer.current=null;if(route){routeLayer.current=L.geoJSON(route.geometry,{style:{color:'#126d65',weight:6,opacity:.9}}).addTo(current);current.fitBounds(routeLayer.current.getBounds(),{padding:[55,55],maxZoom:16});}},[route]);
  useEffect(()=>{const current=map.current;if(!current)return;const p=places.find(p=>p.key===selected);if(p?.located)current.panTo([p.latitude!,p.longitude!]);},[selected]);
  useEffect(()=>{map.current?.fitBounds([[catalog.bounds[1],catalog.bounds[0]],[catalog.bounds[3],catalog.bounds[2]]],{padding:[28,28]});},[resetKey]);
  return <div className="territory-map-shell"><div className="territory-map" ref={container} role="region" aria-label="Mapa de comercios y atractivos de Santa Bárbara, Huequecura y Ralco"/>{message&&<div className={`map-message ${available||places.some(p=>p.located)?'notice':''}`} role="status"><strong>{available?'Cobertura del mapa':'Mapa local pendiente'}</strong><p>{message}</p></div>}<div className="map-key" aria-label="Leyenda"><span><i className="key-business"/>Comercios</span><span><i className="key-interest"/>Atractivos</span>{catalog.station.configured&&<span><i className="key-station"/>Estás aquí</span>}</div></div>;
}
