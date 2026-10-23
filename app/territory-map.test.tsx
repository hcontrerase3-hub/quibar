import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import L from "leaflet";
import TerritoryMap from "./territory-map";
import type { Catalog, Route } from "./map-types";

const mocks = vi.hoisted(() => {
  const map = {
    fitBounds: vi.fn(), panTo: vi.fn(), invalidateSize: vi.fn(), on: vi.fn(), remove: vi.fn(),
    setMinZoom: vi.fn(), setMaxZoom: vi.fn(), getMaxZoom: () => 17,
    project: () => ({ distanceTo: () => 100 }),
  };
  const marker = { addTo: vi.fn(), bindTooltip: vi.fn(), on: vi.fn() };
  marker.addTo.mockReturnValue(marker);
  marker.bindTooltip.mockReturnValue(marker);
  const group = { addTo: vi.fn(), clearLayers: vi.fn() };
  group.addTo.mockReturnValue(group);
  return { map, marker, group, routeBounds: [[-37.8, -72], [-37.7, -71.8]], resize: () => {} };
});
vi.mock("leaflet", async importOriginal => {
  const actual = await importOriginal<{ default: typeof import("leaflet") }>();
  return { default: {
    ...actual.default,
    map: () => mocks.map,
    layerGroup: () => mocks.group,
    control: { zoom: () => ({ addTo: vi.fn() }) },
    tileLayer: () => { const layer = { on: vi.fn(() => layer), addTo: vi.fn() }; return layer; },
    marker: vi.fn(() => mocks.marker),
    geoJSON: () => ({ addTo() { return this; }, getBounds: () => mocks.routeBounds, remove: vi.fn() }),
  } };
});

const catalog: Catalog = {
  places: [], sectors: ["Santa Bárbara"], bounds: [-72.2, -38.05, -71.35, -37.55],
  station: { name: "Tótem de prueba", configured: true, latitude: -37.7272949, longitude: -71.8127746 },
};
const props = { catalog, places: [], selected: null, route: null, suggested: [], resetKey: 0, view: "nearby" as const, onSelect: vi.fn() };
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("ResizeObserver", class { constructor(callback: () => void) { mocks.resize = callback; } observe() {} disconnect() {} });
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ available: true, minZoom: 9, maxZoom: 17, attribution: "Prueba" })))));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("la vista inicial centra un radio aproximado de 5 km en el tótem y deja su etiqueta visible", async () => {
  render(<TerritoryMap {...props} />);
  await waitFor(() => expect(mocks.map.setMaxZoom).toHaveBeenCalled());
  const bounds = mocks.map.fitBounds.mock.lastCall![0] as L.LatLngBounds;
  const station = L.latLng(catalog.station.latitude!, catalog.station.longitude!);
  expect(bounds.getCenter().lat).toBeCloseTo(station.lat, 6);
  expect(bounds.getCenter().lng).toBeCloseTo(station.lng, 6);
  const distance = station.distanceTo([bounds.getNorth(), station.lng]);
  expect(distance).toBeGreaterThan(4900);
  expect(distance).toBeLessThan(5100);
  expect(screen.getByText("Usted está aquí")).toBeTruthy();
  expect(mocks.marker.bindTooltip).toHaveBeenCalledWith("Usted está aquí", expect.objectContaining({ permanent: true }));
});

test("sin tótem muestra el circuito y se acerca al recibir su ubicación", async () => {
  const { rerender } = render(<TerritoryMap {...props} catalog={{ ...catalog, station: { name: "Sin configurar", configured: false, latitude: null, longitude: null } }} />);
  await waitFor(() => expect(mocks.map.setMaxZoom).toHaveBeenCalled());
  const circuit = L.latLngBounds([[-38.05, -72.2], [-37.55, -71.35]]);
  expect((mocks.map.fitBounds.mock.lastCall![0] as L.LatLngBounds).equals(circuit)).toBe(true);
  expect(screen.queryByText("Usted está aquí")).toBeNull();
  rerender(<TerritoryMap {...props} />);
  expect((mocks.map.fitBounds.mock.lastCall![0] as L.LatLngBounds).getCenter().lat).toBeCloseTo(catalog.station.latitude!, 6);
});

test("los refrescos y la selección respetan la vista y los controles distinguen inicio de circuito", async () => {
  const { rerender } = render(<TerritoryMap {...props} />);
  await waitFor(() => expect(mocks.map.setMaxZoom).toHaveBeenCalled());
  mocks.map.fitBounds.mockClear();
  const refreshed = { ...catalog, station: { ...catalog.station }, bounds: [...catalog.bounds] };
  rerender(<TerritoryMap {...props} catalog={refreshed} />);
  expect(mocks.map.fitBounds).not.toHaveBeenCalled();
  const place = { key: "business:test", id: "test", kind: "business" as const, name: "Prueba", category: "Comercio", commune: "Santa Bárbara", sector: "Santa Bárbara", summary: "Prueba", description: "Prueba", latitude: -37.7, longitude: -71.8, located: true, demo: true, hours: "", area: "", photos: [] };
  rerender(<TerritoryMap {...props} catalog={refreshed} places={[place]} selected={place.key} />);
  expect(mocks.map.panTo).toHaveBeenCalledWith([place.latitude, place.longitude]);
  expect(mocks.map.fitBounds).not.toHaveBeenCalled();
  rerender(<TerritoryMap {...props} view="circuit" resetKey={1} />);
  expect((mocks.map.fitBounds.mock.lastCall![0] as L.LatLngBounds).getSouth()).toBe(-38.05);
  rerender(<TerritoryMap {...props} resetKey={2} />);
  expect((mocks.map.fitBounds.mock.lastCall![0] as L.LatLngBounds).getCenter().lat).toBeCloseTo(catalog.station.latitude!, 6);
});

test("una ruta encuadra su trazado y lo mantiene al redimensionar", async () => {
  const { rerender } = render(<TerritoryMap {...props} />);
  await waitFor(() => expect(mocks.map.setMaxZoom).toHaveBeenCalled());
  const route = { geometry: { type: "LineString", coordinates: [] }, stops: [], destination: { key: "business:test" } } as unknown as Route;
  rerender(<TerritoryMap {...props} route={route} />);
  expect(mocks.map.fitBounds).toHaveBeenLastCalledWith(mocks.routeBounds, { padding: [55, 55], maxZoom: 16 });
  mocks.map.fitBounds.mockClear();
  mocks.resize();
  expect(mocks.map.fitBounds).toHaveBeenLastCalledWith(mocks.routeBounds, { padding: [55, 55], maxZoom: 16 });
  rerender(<TerritoryMap {...props} route={route} catalog={{ ...catalog, station: { ...catalog.station } }} />);
  expect(mocks.map.fitBounds).toHaveBeenCalledTimes(1);
});
