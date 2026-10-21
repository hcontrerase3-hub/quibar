import { BedDouble, Coffee, Mountain, Palette, ShoppingBag, Tent, UtensilsCrossed } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type Category = "Alojamiento" | "Gastronomía" | "Artesanía" | "Turismo" | "Comercio";
export type Commune = "Quilaco" | "Santa Bárbara" | "Alto Biobío";
export type Business = {
  id: string; name: string; category: Category; commune: Commune; area: string;
  summary: string; description: string; offerings: string[]; hours: string;
  keywords: string; visual: string; icon: LucideIcon; status: "Aprobado"; demo: boolean;
  latitude: number | null; longitude: number | null; whatsapp: string; featured: boolean;
  photos: { id: number; url: string; alt: string; cover: boolean; order: number }[];
};

const visualIcons: Record<string, LucideIcon> = {
  stay: BedDouble, food: UtensilsCrossed, craft: Palette, outdoors: Mountain,
  coffee: Coffee, shop: ShoppingBag, camp: Tent, textile: Palette,
};

export function asBusiness(item: Omit<Business, "icon">): Business {
  return { ...item, icon: visualIcons[item.visual] ?? ShoppingBag };
}

export const categories: (Category | "Todos")[] = ["Todos", "Alojamiento", "Gastronomía", "Artesanía", "Turismo", "Comercio"];
export const categoryIcons: Record<Category, LucideIcon> = { Alojamiento: BedDouble, Gastronomía: UtensilsCrossed, Artesanía: Palette, Turismo: Mountain, Comercio: ShoppingBag };
export const normalize = (value: string) => value.toLocaleLowerCase("es").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
