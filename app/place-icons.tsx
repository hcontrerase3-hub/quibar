import { renderToStaticMarkup } from 'react-dom/server';
import {
  BedDouble,
  Binoculars,
  Coffee,
  Compass,
  Flag,
  Footprints,
  Landmark,
  Mountain,
  Palette,
  Scissors,
  ShoppingBag,
  Tent,
  Theater,
  Trees,
  UtensilsCrossed,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Place } from './map-types';

export const businessVisualIcons: Record<string, LucideIcon> = {
  stay: BedDouble,
  food: UtensilsCrossed,
  craft: Palette,
  outdoors: Mountain,
  coffee: Coffee,
  shop: ShoppingBag,
  camp: Tent,
  textile: Scissors,
};

export const businessCategoryIcons: Record<string, LucideIcon> = {
  Alojamiento: BedDouble,
  Gastronomía: UtensilsCrossed,
  Artesanía: Palette,
  Turismo: Mountain,
  Comercio: ShoppingBag,
};

export const interestCategoryIcons: Record<string, LucideIcon> = {
  Mirador: Binoculars,
  Naturaleza: Trees,
  Patrimonio: Landmark,
  Plaza: Flag,
  Actividad: Footprints,
  Cultura: Theater,
};

export function placeIconComponent(place: Pick<Place, 'kind' | 'category' | 'visual'>): LucideIcon {
  if (place.kind === 'business') {
    return (place.visual ? businessVisualIcons[place.visual] : undefined)
      ?? businessCategoryIcons[place.category]
      ?? ShoppingBag;
  }
  return interestCategoryIcons[place.category] ?? Compass;
}

const svgCache = new Map<LucideIcon, string>();

export function placeIconSvg(place: Pick<Place, 'kind' | 'category' | 'visual'>): string {
  const Icon = placeIconComponent(place);
  let markup = svgCache.get(Icon);
  if (!markup) {
    markup = renderToStaticMarkup(<Icon size={18} strokeWidth={2.2} aria-hidden="true" />);
    svgCache.set(Icon, markup);
  }
  return markup;
}
