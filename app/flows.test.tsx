import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "./page";
import Admin from "./admin";
import { BusinessLocation } from "./business-detail";
import { asBusiness } from "./data";

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

test("el catálogo no recupera fichas estáticas cuando falla la API", async () => {
  vi.stubGlobal("fetch", vi.fn(() => response({ detail: "No disponible" }, 503)));
  render(<Home />);
  await userEvent.click(screen.getByRole("button", { name: /Explorar comercios/ }));
  await screen.findByText("El catálogo local no está disponible");
  expect(screen.queryAllByRole("button", { name: /Ver ficha de/ })).toHaveLength(0);
});

test("el visitante solo puede abrir las fichas aprobadas de la API", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => url.endsWith("/catalog") ? response([record, { ...record, id: "hidden", name: "Ficha suspendida", status: "Suspendido" }]) : response({ ok: true })));
  render(<Home />);
  await userEvent.click(screen.getByRole("button", { name: /Explorar comercios/ }));
  const card = await screen.findByRole("button", { name: "Ver ficha de Ficha aprobada" });
  expect(screen.queryByText("Ficha suspendida")).toBeNull();
  await userEvent.click(card);
  expect(await screen.findByRole("dialog")).toBeTruthy();
  expect(await screen.findByText("Esta ficha aún no tiene coordenadas verificadas.")).toBeTruthy();
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

test("los QR de ruta y WhatsApp se muestran por separado y registran visualización", async () => {
  const fetchMock = vi.fn((url: string) => response(url.endsWith("/map") ? { available: false } : { ok: true }));
  vi.stubGlobal("fetch", fetchMock);
  render(<BusinessLocation business={asBusiness({ ...record, latitude: -37.68, longitude: -72.01, whatsapp: "+56912345678" })} />);
  await userEvent.click(screen.getByRole("button", { name: /Llevar a mi celular/ }));
  expect(screen.getAllByTitle(/Abrir ruta en mapas|Contactar por WhatsApp/)).toHaveLength(2);
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/metrics"))).toBe(true));
  expect(screen.getByText(/tu celular puede necesitar conexión/)).toBeTruthy();
});


test("el tótem vuelve a la bienvenida tras sesenta segundos sin interacción", () => {
  vi.useFakeTimers();
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
  render(<Home />);
  fireEvent.click(screen.getByRole("button", { name: /Explorar comercios/ }));
  expect(screen.queryByRole("button", { name: /Explorar comercios/ })).toBeNull();
  act(() => { vi.advanceTimersByTime(60001); });
  expect(screen.getByRole("button", { name: /Explorar comercios/ })).toBeTruthy();
});
