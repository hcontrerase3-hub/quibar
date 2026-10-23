import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AdminLocationPicker from "./admin-location-picker";
import Admin from "./admin";

const leaflet = vi.hoisted(() => {
  type Point = { lat: number; lng: number; wrap: () => Point };
  const point = (lat: number, lng: number): Point => ({ lat, lng, wrap() { return this; } });
  const makeMap = () => {
    const handlers: Record<string, (event: { latlng: Point }) => void> = {};
    const map = {
      handlers, fitBounds: vi.fn(), setView: vi.fn(), panTo: vi.fn(), invalidateSize: vi.fn(), remove: vi.fn(),
      getMaxZoom: () => 17, getCenter: () => point(-37.75, -71.9),
      on: vi.fn((name: string, handler: (event: { latlng: Point }) => void) => { handlers[name] = handler; }),
    };
    return map;
  };
  const makeMarker = (_point: [number, number], _options: unknown) => {
    const handlers: Record<string, () => void> = {};
    const marker = {
      handlers, setLatLng: vi.fn(), remove: vi.fn(), getLatLng: () => point(-37.76, -71.91),
      dragging: { enable: vi.fn(), disable: vi.fn() },
      on: vi.fn((name: string, handler: () => void) => { handlers[name] = handler; }),
      addTo: vi.fn(() => marker),
    };
    return marker;
  };
  return { map: vi.fn(makeMap), marker: vi.fn(makeMarker), point };
});
vi.mock("leaflet", () => ({ default: {
  map: leaflet.map, marker: leaflet.marker, latLngBounds: vi.fn(value => value), divIcon: vi.fn(value => value),
  tileLayer: () => { const layer = { on: vi.fn(() => layer), addTo: vi.fn(() => layer) }; return layer; },
} }));

const info = { available: true, minZoom: 9, maxZoom: 17, bounds: [-72.2, -38.05, -71.35, -37.55], attribution: "Mapa de prueba" };
const response = (data: unknown) => Promise.resolve(new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } }));
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal("fetch", vi.fn(() => response(info)));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("una ficha nueva no recibe coordenadas hasta pulsar el mapa", async () => {
  const onChange = vi.fn();
  render(<AdminLocationPicker latitude={null} longitude={null} disabled={false} onChange={onChange} />);
  await screen.findByRole("button", { name: "Usar centro del mapa" });
  expect(leaflet.marker).not.toHaveBeenCalled();
  expect(onChange).not.toHaveBeenCalled();
  act(() => leaflet.map.mock.results[0].value.handlers.click({ latlng: leaflet.point(-37.74, -71.89) }));
  expect(onChange).toHaveBeenCalledWith(-37.74, -71.89);
});

test("carga la ubicación existente, permite arrastrar y refleja la edición manual", async () => {
  const onChange = vi.fn();
  const { rerender } = render(<AdminLocationPicker latitude={-37.7} longitude={-71.8} disabled={false} onChange={onChange} />);
  await waitFor(() => expect(leaflet.marker).toHaveBeenCalled());
  expect(leaflet.marker.mock.calls[0][0]).toEqual([-37.7, -71.8]);
  const pin = leaflet.marker.mock.results[0].value;
  act(() => pin.handlers.dragend());
  expect(onChange).toHaveBeenCalledWith(-37.76, -71.91);
  rerender(<AdminLocationPicker latitude={-37.8} longitude={-71.9} disabled={false} onChange={onChange} />);
  expect(pin.setLatLng).toHaveBeenLastCalledWith([-37.8, -71.9]);
  rerender(<AdminLocationPicker latitude={null} longitude={-71.9} disabled={false} onChange={onChange} />);
  expect(pin.remove).toHaveBeenCalled();
});

test("bloquea la selección y el arrastre mientras se guarda", async () => {
  const onChange = vi.fn();
  const { rerender } = render(<AdminLocationPicker latitude={-37.7} longitude={-71.8} disabled={false} onChange={onChange} />);
  await waitFor(() => expect(leaflet.marker).toHaveBeenCalled());
  rerender(<AdminLocationPicker latitude={-37.7} longitude={-71.8} disabled onChange={onChange} />);
  const pin = leaflet.marker.mock.results[0].value;
  expect(pin.dragging.disable).toHaveBeenCalled();
  expect((screen.getByRole("button", { name: "Usar centro del mapa" }) as HTMLButtonElement).disabled).toBe(true);
  act(() => {
    leaflet.map.mock.results[0].value.handlers.click({ latlng: leaflet.point(-37.74, -71.89) });
    pin.handlers.dragend();
  });
  expect(onChange).not.toHaveBeenCalled();
  expect(pin.setLatLng).toHaveBeenLastCalledWith([-37.7, -71.8]);
});

test("permite elegir el centro sin arrastrar el marcador", async () => {
  const onChange = vi.fn();
  render(<AdminLocationPicker latitude={null} longitude={null} disabled={false} onChange={onChange} />);
  fireEvent.click(await screen.findByRole("button", { name: "Usar centro del mapa" }));
  expect(onChange).toHaveBeenCalledWith(-37.75, -71.9);
});

test.each(["ausente", "error"])("con mapa %s mantiene un aviso para la entrada manual", async mode => {
  vi.stubGlobal("fetch", vi.fn(() => mode === "ausente" ? response({ available: false }) : Promise.reject(Error("offline"))));
  render(<AdminLocationPicker latitude={null} longitude={null} disabled={false} onChange={vi.fn()} />);
  await screen.findByText(/Puedes introducir las coordenadas manualmente/);
  expect(leaflet.map).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Usar centro del mapa" })).toBeNull();
});

test("el panel guarda el punto elegido, exige revisión y limpia el mapa al cambiar de tienda", async () => {
  const business = {
    id: "first", name: "Tienda de prueba", category: "Gastronomía", commune: "Santa Bárbara", sector: "Santa Bárbara",
    area: "Dirección de prueba", summary: "Resumen de prueba", description: "Descripción de prueba", offerings: ["Café"],
    hours: "09:00–18:00", keywords: "", visual: "shop", status: "Pendiente", latitude: -37.7, longitude: -71.8,
    location_source: "Fuente de prueba", location_verified: true, whatsapp: "", legal_name: "", tax_id: "", demo: true, featured: false, photos: [],
  };
  let saved = business;
  const second = { ...business, id: "second", name: "Otra tienda", latitude: null, longitude: null, location_verified: false };
  const fetchMock = vi.fn((url: string, options: RequestInit = {}) => {
    if (url.endsWith("/map")) return response(info);
    if (url.endsWith("/session")) return response({ id: 1, name: "Admin", role: "Administrador", csrf: "test-csrf" });
    if (url.endsWith("/lookups")) return response({ communes: ["Santa Bárbara"], categories: ["Gastronomía"] });
    if (url.endsWith("/metrics")) return response([]);
    if (options.method === "PUT") { saved = JSON.parse(String(options.body)); return response(saved); }
    return response([saved, second]);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<Admin />);
  await screen.findByRole("button", { name: /Tienda de prueba/ });
  fireEvent.click(screen.getByRole("button", { name: /Tienda de prueba/ }));
  await waitFor(() => expect(leaflet.marker).toHaveBeenCalled());
  act(() => leaflet.map.mock.results[0].value.handlers.click({ latlng: leaflet.point(-37.74, -71.89) }));
  expect((screen.getByLabelText("Latitud") as HTMLInputElement).value).toBe("-37.74");
  expect((screen.getByLabelText("Longitud") as HTMLInputElement).value).toBe("-71.89");
  expect((screen.getByLabelText("Ubicación verificada para el mapa") as HTMLInputElement).checked).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
  await screen.findByText(/Ficha guardada/);
  expect(saved).toMatchObject({ latitude: -37.74, longitude: -71.89, location_verified: false });
  const update = fetchMock.mock.calls.find(([, options]) => options?.method === "PUT")!;
  expect(new Headers(update[1]?.headers).get("x-csrf-token")).toBe("test-csrf");
  fireEvent.click(screen.getByLabelText("Ubicación verificada para el mapa"));
  fireEvent.change(screen.getByLabelText("Latitud"), { target: { value: "-37.75" } });
  expect((screen.getByLabelText("Ubicación verificada para el mapa") as HTMLInputElement).checked).toBe(false);
  const oldMap = leaflet.map.mock.results[0].value;
  fireEvent.click(screen.getByRole("button", { name: /Otra tienda/ }));
  await waitFor(() => expect(leaflet.map).toHaveBeenCalledTimes(2));
  expect(oldMap.remove).toHaveBeenCalled();
  expect((screen.getByLabelText("Latitud") as HTMLInputElement).value).toBe("");
  expect(leaflet.marker).toHaveBeenCalledTimes(1);
});
