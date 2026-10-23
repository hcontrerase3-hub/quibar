import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "./page";
import Admin from "./admin";
import { BusinessLocation } from "./business-detail";
import { routeUrl } from "./map-types";
import { asBusiness } from "./data";

vi.mock("./territory-map", () => ({ default: ({ view, resetKey }: { view: string; resetKey: number }) => <div aria-label="Mapa del circuito" data-view={view} data-reset-key={resetKey} /> }));
vi.mock("leaflet", () => ({ default: {
  map: () => { const map = { setView: () => map, setMinZoom: () => map, setMaxZoom: () => map, invalidateSize: () => {}, remove: () => {} }; return map; },
  circleMarker: () => ({ addTo: () => {} }),
  tileLayer: () => { const layer = { on: () => layer, addTo: () => layer }; return layer; },
} }));
const record = { id: "sample", name: "Ficha aprobada", category: "Gastronomía" as const, commune: "Quilaco" as const,
  area: "Centro de Quilaco", summary: "Una ficha de prueba", description: "Descripción del negocio de prueba",
  offerings: ["Café"], hours: "09:00–18:00", keywords: "café", visual: "coffee", status: "Aprobado" as const,
  demo: true, latitude: null, longitude: null, whatsapp: "", featured: false, photos: [], legal_name: "", tax_id: "" };
const response = (data: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } }));
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

const place = { ...record, commune: "Santa Bárbara", sector: "Huequecura", key: "business:sample", kind: "business", located: true, demo: false, latitude: -37.74, longitude: -71.89 };
const station = { name: "Tótem sintético", configured: true, latitude: -37.67, longitude: -72.02 };
const catalog = { places: [place], sectors: ["Santa Bárbara", "Huequecura", "Ralco"], bounds: [-72.2,-38.05,-71.35,-37.55], station };
const route = { geometry: { type: "LineString", coordinates: [[-72.02,-37.67],[-71.89,-37.74]] }, distance_m: 1500, duration_s: 1200, maneuvers:[{instruction:"Sigue el camino de prueba",distance_m:1500,duration_s:1200}],origin:station,destination:place,stops:[],profile:"walking",text:"Recorrido sintético para la prueba",narration_id:"test-narration",notice:"Estimación sin tráfico." };

test("el mapa es la pantalla inicial y la API caída no publica copias estáticas", async () => {
  vi.stubGlobal("fetch", vi.fn(() => response({ detail: "No disponible" }, 503)));
  render(<Home />);
  await screen.findByText(/El catálogo local no está disponible/);
  expect(screen.queryByRole("button", { name: /Explorar comercios/ })).toBeNull();
  expect(screen.queryAllByRole("button", { name: /Ver ficha de/ })).toHaveLength(0);
});

test("solo se abren fichas aprobadas del circuito y las no ubicadas no ofrecen ruta", async () => {
  vi.stubGlobal("fetch", vi.fn(() => response({ ...catalog, places:[{...place, located:false,latitude:null,longitude:null},{...place,key:"hidden",name:"Ficha suspendida",status:"Suspendido"}] })));
  render(<Home />);
  await userEvent.click(await screen.findByRole("button", {name:"Ver ficha de Ficha aprobada"}));
  expect(screen.queryByText("Ficha suspendida")).toBeNull();
  expect(screen.getByText("Esta ficha aún no tiene coordenadas verificadas.")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Cómo llegar"})).toBeNull();
});

test("las paradas se sugieren automáticamente y solo se añaden al confirmar", async () => {
  const other={...place,key:"interest:other",id:"other",kind:"interest",name:"Atractivo sintético",category:"Mirador"};
  const calls: {url:string; body:unknown}[]=[];
  vi.stubGlobal("fetch",vi.fn((url:string,options:RequestInit={})=>{
    const body=options.body?JSON.parse(String(options.body)):{};calls.push({url,body});
    if(url.endsWith("/places"))return response({...catalog,places:[place,other]});
    if(url.endsWith("/suggestions"))return response({suggestions:body.stops.length?[]:[{place:other,extra_duration_s:120,stop_order:[other.key]}],text:"Una parada en el camino",narration_id:"suggestion-narration"});
    if(url.endsWith("/narration"))return response({text:"Una parada en el camino",narration_id:"narration",mode:"basico"});
    if(url.endsWith("/routes"))return response({...route,stops:body.stops.length?[other]:[]});
    return response({ok:true});
  }));
  render(<Home />);await userEvent.click(await screen.findByRole("button",{name:"Ver ficha de Ficha aprobada"}));
  await userEvent.click(screen.getByRole("button",{name:/Cómo llegar/}));
  const add=await screen.findByRole("button",{name:/Añadir parada/});
  expect(calls.filter(c=>c.url.endsWith("/routes"))).toHaveLength(1);
  expect((calls.find(c=>c.url.endsWith("/routes"))!.body as {stops:string[]}).stops).toEqual([]);
  await userEvent.click(add);
  await waitFor(()=>expect(calls.filter(c=>c.url.endsWith("/routes"))).toHaveLength(2));
  expect((calls.filter(c=>c.url.endsWith("/routes"))[1].body as {stops:string[]}).stops).toEqual([other.key]);
  expect(await screen.findByRole("button",{name:"Quitar parada Atractivo sintético"})).toBeTruthy();
});

test("el QR del recorrido conserva origen, modalidad y paradas", () => {
  const stops = [{...place,kind:"business"}, {...place,kind:"interest",latitude:-37.75,longitude:-71.88}, {...place,kind:"business",latitude:-37.76,longitude:-71.87}];
  const params=new URL(routeUrl({...route, geometry:{type:"LineString",coordinates:[]}, profile:"driving",stops} as Parameters<typeof routeUrl>[0])).searchParams;
  expect(params.get("origin")).toBe("-37.67,-72.02");expect(params.get("waypoints")).toBe("-37.74,-71.89|-37.75,-71.88|-37.76,-71.87");expect(params.get("travelmode")).toBe("driving");
});

test.each(["business", "interest"] as const)("un lugar ficticio de tipo %s permite demostrar la ruta y conserva su identificación", async kind => {
  const demo = { ...place, kind, key: `${kind}:sample`, demo: true };
  const demoRoute = { ...route, destination: demo, text: "Recorrido de demostración: incluye lugares ficticios." };
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    if (url.endsWith("/places")) return response({ ...catalog, places: [demo] });
    if (url.endsWith("/suggestions")) return response({ suggestions: [], text: demoRoute.text });
    if (url.endsWith("/narration")) return response({ text: demoRoute.text, narration_id: "demo-narration", mode: "basico" });
    if (url.endsWith("/routes")) return response(demoRoute);
    return response({ ok: true });
  }));
  render(<Home />);
  fireEvent.click(await screen.findByRole("button", { name: "Ver ficha de Ficha aprobada" }));
  expect(screen.getByText(kind === "business" ? "Ubicación de demostración · negocio ficticio" : "Ubicación de demostración · lugar ficticio")).toBeTruthy();
  expect(screen.queryByText(/sin ubicación verificada/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Cómo llegar" }));
  const trip = await screen.findByRole("region", { name: "Tu recorrido" });
  expect(within(trip).getAllByText("Recorrido de demostración: incluye lugares ficticios.").length).toBeGreaterThan(0);
  fireEvent.click(within(trip).getByRole("button", { name: "Llevar recorrido al celular" }));
  expect(within(trip).getByTitle("Abrir recorrido con paradas en Google Maps")).toBeTruthy();
});

test("un recorrido a un destino real identifica las paradas ficticias seleccionadas", async () => {
  const stop = { ...place, key: "business:demo-stop", id: "demo-stop", name: "Parada ficticia", demo: true };
  vi.stubGlobal("fetch", vi.fn((url: string, options: RequestInit = {}) => {
    const body = options.body ? JSON.parse(String(options.body)) : {};
    if (url.endsWith("/places")) return response({ ...catalog, places: [place, stop] });
    if (url.endsWith("/suggestions")) return response({ suggestions: body.stops.length ? [] : [{ place: stop, extra_duration_s: 120, stop_order: [stop.key] }] });
    if (url.endsWith("/narration")) return response({ text: "Texto de prueba", narration_id: "demo-narration", mode: "basico" });
    if (url.endsWith("/routes")) return response({ ...route, stops: body.stops.length ? [stop] : [] });
    return response({ ok: true });
  }));
  render(<Home />);
  fireEvent.click(await screen.findByRole("button", { name: "Ver ficha de Ficha aprobada" }));
  fireEvent.click(screen.getByRole("button", { name: "Cómo llegar" }));
  const add = await screen.findByRole("button", { name: /Añadir parada/ });
  expect(screen.getByText("Negocio ficticio de demostración")).toBeTruthy();
  expect(screen.queryByText("Recorrido de demostración: incluye lugares ficticios.")).toBeNull();
  fireEvent.click(add);
  await screen.findByRole("button", { name: "Quitar parada Parada ficticia" });
  expect(screen.getByText("Recorrido de demostración: incluye lugares ficticios.")).toBeTruthy();
});

test("un operador guarda como pendiente y envía la protección CSRF", async () => {
  const account = { id: 2, name: "Operador", email: "operator@example.test", role: "Operador Territorial", csrf: "test-csrf" };
  const requests: { url: string; options: RequestInit }[] = [];
  vi.stubGlobal("fetch", vi.fn((url: string, options: RequestInit = {}) => {
    requests.push({ url, options });
    if (url.endsWith("/session")) return response(account);
    if (url.endsWith("/lookups")) return response({ communes: ["Quilaco"], categories: ["Gastronomía"] });
    if (url.endsWith("/metrics")) return response([]);
    if (url.endsWith("/businesses/sample")) return response({ ...record, status: "Pendiente" });
    return response([record]);
  }));
  render(<Admin />);
  await userEvent.click(await screen.findByRole("button", { name: /Ficha aprobada/ }));
  const status = screen.getByLabelText("Estado") as HTMLSelectElement;
  expect(status.value).toBe("Pendiente");
  expect(within(status).queryByRole("option", { name: "Aprobado" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
  await screen.findByText(/Ficha guardada/);
  const update = requests.find(req => req.options.method === "PUT")!;
  expect(new Headers(update.options.headers).get("x-csrf-token")).toBe("test-csrf");
  expect(JSON.parse(String(update.options.body)).status).toBe("Pendiente");
});

test("al verificar una ubicación enumera los campos faltantes y permite corregirlos antes de guardar", async () => {
  const saved = { ...record, status: "Pendiente", sector: "", location_source: "", location_verified: false };
  const fetchMock = vi.fn((url: string, options: RequestInit = {}) => {
    if (url.endsWith("/session")) return response({ id: 1, name: "Admin", role: "Administrador", csrf: "test-csrf" });
    if (url.endsWith("/lookups")) return response({ communes: ["Quilaco"], categories: ["Gastronomía"] });
    if (url.endsWith("/metrics")) return response([]);
    if (url.endsWith("/map")) return response({ available: false });
    if (options.method === "PUT") return response({ ...saved, ...JSON.parse(String(options.body)) });
    return response([saved]);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<Admin />);
  fireEvent.click(await screen.findByRole("button", { name: /Ficha aprobada/ }));
  fireEvent.click(screen.getByLabelText("Ubicación verificada para el mapa"));
  fireEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
  const alert = await screen.findByRole("alert");
  for (const label of ["Sector del circuito", "Fuente de ubicación", "Latitud", "Longitud"]) {
    expect(within(alert).getByRole("button", { name: `${label}: Completa este campo.` })).toBeTruthy();
    expect(screen.getByLabelText(label).getAttribute("aria-invalid")).toBe("true");
  }
  expect(document.activeElement).toBe(screen.getByLabelText("Sector del circuito"));
  expect(fetchMock.mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
  fireEvent.click(within(alert).getByRole("button", { name: "Fuente de ubicación: Completa este campo." }));
  expect(document.activeElement).toBe(screen.getByLabelText("Fuente de ubicación"));
  fireEvent.change(screen.getByLabelText("Fuente de ubicación"), { target: { value: " abcd " } });
  expect(within(screen.getByRole("alert")).getByText("Fuente de ubicación: Escribe al menos 5 caracteres.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Fuente de ubicación"), { target: { value: "Confirmado por el dueño" } });
  fireEvent.change(screen.getByLabelText("Sector del circuito"), { target: { value: "Santa Bárbara" } });
  fireEvent.change(screen.getByLabelText("Latitud"), { target: { value: "-37.7" } });
  fireEvent.change(screen.getByLabelText("Longitud"), { target: { value: "-71.8" } });
  fireEvent.click(screen.getByLabelText("Ubicación verificada para el mapa"));
  expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
  await screen.findByText(/Ficha guardada/);
  expect(fetchMock.mock.calls.some(([, options]) => options?.method === "PUT")).toBe(true);
});

test("una ficha nueva muestra todos los campos obligatorios vacíos", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    if (url.endsWith("/session")) return response({ id: 1, name: "Admin", role: "Administrador", csrf: "test-csrf" });
    if (url.endsWith("/lookups")) return response({ communes: ["Santa Bárbara"], categories: ["Gastronomía"] });
    if (url.endsWith("/map")) return response({ available: false });
    return response([]);
  }));
  render(<Admin />);
  fireEvent.click(await screen.findByRole("button", { name: "+ Nueva ficha" }));
  fireEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
  const alert = await screen.findByRole("alert");
  for (const label of ["Nombre comercial", "Resumen", "Descripción", "Servicios o productos (uno por línea)", "Dirección o referencia rural", "Horario"]) {
    expect(within(alert).getByRole("button", { name: `${label}: Completa este campo.` })).toBeTruthy();
  }
  expect(within(alert).queryByText(/Fuente de ubicación/)).toBeNull();
});

test("los errores de validación de la API conservan el motivo del rechazo", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string, options: RequestInit = {}) => {
    if (url.endsWith("/session")) return response({ id: 1, name: "Admin", role: "Administrador", csrf: "test-csrf" });
    if (url.endsWith("/lookups")) return response({ communes: ["Quilaco"], categories: ["Gastronomía"] });
    if (url.endsWith("/map")) return response({ available: false });
    if (url.endsWith("/metrics")) return response([]);
    if (options.method === "PUT") return response({ detail: [{ loc: ["body"], msg: "Value error, Verifica coordenadas, sector y fuente antes de publicar en el mapa" }] }, 422);
    return response([record]);
  }));
  render(<Admin />);
  fireEvent.click(await screen.findByRole("button", { name: /Ficha aprobada/ }));
  fireEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
  expect((await screen.findByRole("alert")).textContent).toBe("Verifica coordenadas, sector y fuente antes de publicar en el mapa");
});

test("los QR de ruta y WhatsApp se muestran por separado y registran visualización", async () => {
  const fetchMock = vi.fn((url: string) => response(url.endsWith("/map") ? { available: false } : { ok: true }));
  vi.stubGlobal("fetch", fetchMock);
  render(<BusinessLocation business={asBusiness({ ...record, latitude: -37.68, longitude: -72.01, whatsapp: "+56912345678" })} />);
  await userEvent.click(screen.getByRole("button", { name: /Llevar a mi celular/ }));
  expect(screen.getAllByTitle(/Abrir ruta en mapas|Contactar por WhatsApp/)).toHaveLength(2);
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/metrics"))).toBe(true));
  expect(screen.getByText(/tu celular puede necesitar conexión/)).toBeTruthy();
});


test("el tótem restablece búsqueda y filtros después de sesenta segundos", () => {
  vi.useFakeTimers();vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
  render(<Home />);
  fireEvent.click(screen.getByRole("button", { name: "Ver circuito" }));
  expect(screen.getByLabelText("Mapa del circuito").getAttribute("data-view")).toBe("circuit");
  fireEvent.change(screen.getByRole("textbox",{name:"Buscar lugares"}),{target:{value:"prueba"}});
  fireEvent.click(screen.getByRole("button",{name:"Ralco"}));
  act(()=>{vi.advanceTimersByTime(60001);});
  expect((screen.getByRole("textbox",{name:"Buscar lugares"}) as HTMLInputElement).value).toBe("");
  expect(screen.getByRole("button",{name:"Todo el circuito"}).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByLabelText("Mapa del circuito").getAttribute("data-view")).toBe("nearby");
});

test("ver circuito muestra toda la zona y volver al inicio recupera la vista del tótem", async () => {
  vi.stubGlobal("fetch", vi.fn(() => response(catalog)));
  render(<Home />);
  const map = await screen.findByLabelText("Mapa del circuito");
  expect(map.getAttribute("data-view")).toBe("nearby");
  fireEvent.click(screen.getByRole("button", { name: "Ver circuito" }));
  expect(map.getAttribute("data-view")).toBe("circuit");
  const previous = map.getAttribute("data-reset-key");
  fireEvent.click(screen.getByRole("button", { name: "Volver al inicio" }));
  expect(map.getAttribute("data-view")).toBe("nearby");
  expect(map.getAttribute("data-reset-key")).not.toBe(previous);
});
