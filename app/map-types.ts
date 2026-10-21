export const sectors = ['Santa Bárbara', 'Huequecura', 'Ralco'] as const;
export type Place = { key: string; id: string; kind: 'business' | 'interest'; name: string; category: string; commune: string; sector: string; summary: string; description: string; latitude: number | null; longitude: number | null; located: boolean; demo: boolean; hours: string; area: string; access?: string; whatsapp?: string; photos: {url: string; alt: string}[] };
export type Station = {name: string; configured: boolean; latitude: number | null; longitude: number | null};
export type Catalog = {places: Place[]; sectors: string[]; bounds: number[]; station: Station};
export type RouteRequest = {destination: string; profile: 'walking' | 'driving'; stops: string[]};
export type Suggestion = {place: Place; extra_duration_s: number; stop_order: string[]};
export type Route = {geometry: {type: 'LineString'; coordinates: [number, number][]}; distance_m: number; duration_s: number; maneuvers: {instruction:string; distance_m:number; duration_s:number}[]; origin: Station; destination: Place; stops: Place[]; profile: 'walking' | 'driving'; text: string; narration_id: string; notice: string};
export const minutes = (seconds: number) => `${Math.max(1, Math.round(seconds / 60))} min`;
export function routeUrl(route: Route) {
  const params = new URLSearchParams({api:'1',origin:`${route.origin.latitude},${route.origin.longitude}`,destination:`${route.destination.latitude},${route.destination.longitude}`,travelmode:route.profile});
  if (route.stops.length) params.set('waypoints',route.stops.map(p=>`${p.latitude},${p.longitude}`).join('|'));
  return `https://www.google.com/maps/dir/?${params}`;
}
