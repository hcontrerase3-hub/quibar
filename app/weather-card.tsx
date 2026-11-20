import { useEffect, useState } from 'react';
import { Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSun, Snowflake, Sun, Wind } from 'lucide-react';

export type WeatherData = {
  available: boolean;
  code?: string;
  city?: string;
  temperature?: string;
  condition?: string;
  humidity?: string;
  updated_at?: string;
};

const REFRESH_MS = 10 * 60 * 1000;

export type WeatherKind = 'storm' | 'drizzle' | 'rain' | 'snow' | 'fog' | 'wind' | 'partly-cloudy' | 'cloudy' | 'clear';

function weatherKind(condition: string): WeatherKind {
  const text = condition.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  if (text.includes('tormenta') || text.includes('electric')) return 'storm';
  if (text.includes('llovizna')) return 'drizzle';
  if (text.includes('lluvia') || text.includes('chubasco') || text.includes('precipit')) return 'rain';
  if (text.includes('nieve') || text.includes('aguanieve')) return 'snow';
  if (text.includes('niebla') || text.includes('neblina') || text.includes('bruma')) return 'fog';
  if (text.includes('viento')) return 'wind';
  if (text.includes('parcial')) return 'partly-cloudy';
  if (text.includes('nublado') || text.includes('cubierto')) return 'cloudy';
  if (text.includes('despejado') || text.includes('soleado')) return 'clear';
  return 'partly-cloudy';
}

const WEATHER_ICONS = {
  storm: CloudLightning,
  drizzle: CloudDrizzle,
  rain: CloudRain,
  snow: Snowflake,
  fog: CloudFog,
  wind: Wind,
  'partly-cloudy': CloudSun,
  cloudy: Cloud,
  clear: Sun,
};

function formatTemperature(raw: string) {
  const numeric = Number.parseFloat(raw.replace(',', '.'));
  return Number.isFinite(numeric) ? `${Math.round(numeric)} °C` : `${raw.trim()} °C`;
}

/** Tarjeta discreta con el clima actual obtenido desde Open-Meteo a través de la API local. */
export default function WeatherCard() {
  const [weather, setWeather] = useState<WeatherData | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;

    async function load() {
      if (inFlight || document.hidden) return;
      inFlight = true;
      try {
        const response = await fetch('/api/quibar/weather', { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) return;
        const data = (await response.json()) as WeatherData;
        if (!controller.signal.aborted && data?.available && typeof data.temperature === 'string' && data.temperature.trim()) {
          setWeather(data);
        }
      } catch {
        /* Silent fallback: the map stays uncluttered when weather is unavailable. */
      } finally {
        inFlight = false;
      }
    }

    void load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  if (!weather?.available || !weather.temperature) return null;

  const condition = weather.condition?.trim() || 'Clima actual';
  const city = weather.city?.trim() || '';
  const humidity = weather.humidity?.trim() ? `${weather.humidity.trim()}% hum.` : '';
  const meta = [city, humidity].filter(Boolean).join(' · ');
  const kind = weatherKind(condition);
  const Icon = WEATHER_ICONS[kind];
  const hasDrops = kind === 'rain' || kind === 'drizzle' || kind === 'storm';
  const hasFlakes = kind === 'snow';
  const hasGlow = kind === 'clear' || kind === 'partly-cloudy';

  return (
    <aside className="map-weather" data-weather={kind} aria-label="Clima actual">
      <span className="map-weather-icon" aria-hidden="true">
        {hasGlow && <span className="weather-glow" />}
        <Icon size={20} />
        {hasDrops && <span className="weather-drops"><i /><i /><i /></span>}
        {hasFlakes && <span className="weather-flakes"><i /><i /><i /></span>}
      </span>
      <div className="map-weather-body">
        <div className="map-weather-main">
          <strong>{formatTemperature(weather.temperature)}</strong>
          <span>{condition}</span>
        </div>
        {meta && <div className="map-weather-meta">{meta}</div>}
      </div>
    </aside>
  );
}
