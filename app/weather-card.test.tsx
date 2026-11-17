import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import WeatherCard from "./weather-card";

const jsonResponse = (data: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("muestra la tarjeta discreta del clima cuando la API responde", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      jsonResponse({
        available: true,
        city: "Los Nogales, Santa Bárbara",
        temperature: "18.4",
        condition: "Parcialmente nublado",
        humidity: "65",
      })
    )
  );
  render(<WeatherCard />);
  const card = await screen.findByLabelText("Clima actual");
  expect(card.textContent).toContain("18 °C");
  expect(card.textContent).toContain("Parcialmente nublado");
  expect(card.textContent).toContain("Los Nogales, Santa Bárbara · 65% hum.");
});

test("oculta la tarjeta si el clima no está disponible o falla la conexión", async () => {
  vi.stubGlobal("fetch", vi.fn(() => jsonResponse({ available: false })));
  const { rerender } = render(<WeatherCard />);
  await Promise.resolve();
  expect(screen.queryByLabelText("Clima actual")).toBeNull();

  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("Sin conexión"))));
  rerender(<WeatherCard />);
  await Promise.resolve();
  expect(screen.queryByLabelText("Clima actual")).toBeNull();
});
