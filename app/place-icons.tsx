import { renderToStaticMarkup } from 'react-dom/server';
import {
  ColbunActivityIcon,
  ColbunCampIcon,
  ColbunCoffeeIcon,
  ColbunCraftIcon,
  ColbunCultureIcon,
  ColbunFoodIcon,
  ColbunHeritageIcon,
  ColbunMapIcon,
  ColbunNatureIcon,
  ColbunOutdoorsIcon,
  ColbunShopIcon,
  ColbunStayIcon,
  ColbunTextileIcon,
  ColbunViewpointIcon,
  type ColbunIconComponent,
} from './colbun-icons';
import type { Place } from './map-types';

export const businessVisualIcons: Record<string, ColbunIconComponent> = {
  stay: ColbunStayIcon,
  food: ColbunFoodIcon,
  craft: ColbunCraftIcon,
  outdoors: ColbunOutdoorsIcon,
  coffee: ColbunCoffeeIcon,
  shop: ColbunShopIcon,
  camp: ColbunCampIcon,
  textile: ColbunTextileIcon,
};

export const businessCategoryIcons: Record<string, ColbunIconComponent> = {
  Alojamiento: ColbunStayIcon,
  Gastronomía: ColbunFoodIcon,
  Artesanía: ColbunCraftIcon,
  Turismo: ColbunOutdoorsIcon,
  Comercio: ColbunShopIcon,
};

export const interestCategoryIcons: Record<string, ColbunIconComponent> = {
  Mirador: ColbunViewpointIcon,
  Naturaleza: ColbunNatureIcon,
  Patrimonio: ColbunHeritageIcon,
  Plaza: ColbunFoodIcon,
  Actividad: ColbunActivityIcon,
  Cultura: ColbunCultureIcon,
};

export function placeIconComponent(place: Pick<Place, 'kind' | 'category' | 'visual'>): ColbunIconComponent {
  if (place.kind === 'business') {
    return (place.visual ? businessVisualIcons[place.visual] : undefined)
      ?? businessCategoryIcons[place.category]
      ?? ColbunShopIcon;
  }
  return interestCategoryIcons[place.category] ?? ColbunMapIcon;
}

const svgCache = new Map<ColbunIconComponent, string>();

export function placeIconSvg(place: Pick<Place, 'kind' | 'category' | 'visual'>): string {
  const Icon = placeIconComponent(place);
  let markup = svgCache.get(Icon);
  if (!markup) {
    markup = renderToStaticMarkup(<Icon size={30} />);
    svgCache.set(Icon, markup);
  }
  return markup;
}
