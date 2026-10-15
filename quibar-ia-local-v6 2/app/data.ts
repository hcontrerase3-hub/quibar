import catalog from "../data/catalog.json";
import { BedDouble, Coffee, Mountain, Palette, ShoppingBag, Tent, UtensilsCrossed } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type Category = "Alojamiento" | "Gastronomía" | "Artesanía" | "Turismo" | "Comercio";
export type Commune = "Quilaco" | "Santa Bárbara";
export type Business = {
  id: string; name: string; category: Category; commune: Commune; area: string;
  summary: string; description: string; offerings: string[]; hours: string;
  keywords: string; visual: string; icon: LucideIcon; status: "Aprobado"; demo: boolean;
};

const visualIcons: Record<string, LucideIcon> = {
  stay: BedDouble, food: UtensilsCrossed, craft: Palette, outdoors: Mountain,
  coffee: Coffee, shop: ShoppingBag, camp: Tent, textile: Palette,
};

// Una sola fuente de datos para la interfaz y la API local.
export const businesses: Business[] = catalog
  .filter(item => item.status === "Aprobado")
  .map(item => ({ ...item, category: item.category as Category,
    commune: item.commune as Commune, status: "Aprobado" as const,
    icon: visualIcons[item.visual] ?? ShoppingBag }));

export function asBusiness(item: Omit<Business, "icon">): Business {
  return { ...item, icon: visualIcons[item.visual] ?? ShoppingBag };
}

export const categories: (Category | "Todos")[] = ["Todos", "Alojamiento", "Gastronomía", "Artesanía", "Turismo", "Comercio"];
export const categoryIcons: Record<Category, LucideIcon> = { Alojamiento: BedDouble, Gastronomía: UtensilsCrossed, Artesanía: Palette, Turismo: Mountain, Comercio: ShoppingBag };
export const normalize = (value: string) => value.toLocaleLowerCase("es").normalize("NFD").replace(/[\u0300-\u036f]/g, "");

export function recommend(raw: string, approvedCatalog: Business[] = businesses) {
  const q = normalize(raw.trim());
  if (!q) return { matches: [] as Business[], response: "Cuéntame qué te gustaría hacer o encontrar por aquí." };
  const patterns: [Category, RegExp][] = [
    ["Alojamiento", /aloj|dorm|cabana|camp|hosped|quedar|estad/],
    ["Gastronomía", /comer|comida|almorz|restaur|cafe|desayun|pastel|once|hambre/],
    ["Artesanía", /artesan|regalo|tejid|recuerdo|souvenir/],
    ["Turismo", /pase|tour|turis|sender|camin|trek|excurs|aventur/],
    ["Comercio", /tienda|compr|almacen|abarrot|mercad/],
  ];
  const category = patterns.find(([, regex]) => regex.test(q))?.[0];
  const commune = q.includes("santa barbara") ? "Santa Bárbara" : q.includes("quilaco") ? "Quilaco" : undefined;
  const known = approvedCatalog.filter(b => q.includes(normalize(b.name)));
  if (known.length) return { matches: known.slice(0, 3), response: "Encontré esta ficha en el catálogo de ejemplo aprobado. Tócala para consultar sus datos." };
  if (/\b(existe|conoces|hablame de|cuentame de|busco el negocio|busco la empresa)\b/.test(q))
    return { matches: [], response: "No cuento con ese registro en el catálogo de ejemplo aprobado. Puedes explorar las fichas disponibles." };
  const stop = new Set(["quiero", "busco", "para", "algo", "donde", "estar", "opciones", "cerca", "conocer", "santa", "barbara", "quilaco", "lugar", "lugares", "comer", "comida", "alojamiento", "alojarme", "cabanas", "artesania", "turismo", "regalo", "pasear", "comprar", "ideas", "rico", "rica", "hecho", "mano", "horario", "hora", "tienen", "ofrece", "tomar", "tomarme", "beber", "beberme", "gustaria", "quisiera", "podria"]);
  const tokens = q.split(/[^a-z0-9]+/).filter(word => word.length > 3 && !stop.has(word));
  const ranked = approvedCatalog.map(b => {
    const haystack = normalize(b.name + " " + b.category + " " + b.summary + " " + b.offerings.join(" ") + " " + b.keywords);
    const tokenScore = tokens.reduce((score, word) => score + (haystack.includes(word) ? 1 : 0), 0);
    return { b, score: (category === b.category ? 4 : 0) + tokenScore };
  }).filter(({ b, score }) => (!commune || b.commune === commune) && (!category || b.category === category) && (tokens.length === 0 ? !!(category || commune) : tokens.every(word => normalize(b.name + " " + b.summary + " " + b.offerings.join(" ") + " " + b.keywords).includes(word))))
    .sort((a, b) => b.score - a.score).slice(0, 3).map(({ b }) => b);
  if (!ranked.length) return { matches: [], response: "No encuentro una opción que coincida en este catálogo de ejemplo. Prueba con alojamiento, comida, artesanía o paseos." };
  return { matches: ranked, response: "Encontré " + (ranked.length === 1 ? "esta opción" : "estas opciones") + (commune ? " en " + commune : "") + " en el catálogo de ejemplo. Puedes abrir una ficha para ver más detalles." };
}
