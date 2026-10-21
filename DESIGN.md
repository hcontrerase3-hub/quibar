---
name: Quíbar
description: Sistema existente de la interfaz táctil y administración de Quíbar.
colors:
  primary: "#0b6661"
  map-action: "#176d60"
  map-deep: "#174f45"
  interest: "#a15a29"
  station: "#235ea4"
  focus: "#bb6722"
  map-background: "#f5f6f0"
  surface: "#fff"
  map-foreground: "#163f3a"
  map-border: "#dbe4dc"
  message-background: "#edf4e9"
  suggestion-background: "#f4f0e3"
typography:
  controls:
    fontFamily: "Arial, Helvetica, sans-serif"
    fontSize: "14px"
    fontWeight: 700
  place-title:
    fontFamily: "Arial, Helvetica, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.3
  description:
    fontFamily: "Arial, Helvetica, sans-serif"
    fontSize: "14px"
    lineHeight: 1.65
rounded:
  control: "8px"
  container: "10px"
  overlay: "12px"
  sector: "24px"
spacing:
  compact: "8px"
  control: "12px"
  message: "16px"
  panel: "20px"
  panel-inline: "22px"
components:
  map-primary:
    backgroundColor: "{colors.map-action}"
    textColor: "{colors.surface}"
    typography: "{typography.controls}"
    rounded: "{rounded.control}"
    padding: "12px"
  map-primary-hover:
    backgroundColor: "#135647"
  sector-selected:
    backgroundColor: "{colors.map-deep}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sector}"
    padding: "0 17px"
  suggestion-action:
    backgroundColor: "{colors.suggestion-background}"
    textColor: "#694c23"
    padding: "0 11px"
  guide-message:
    backgroundColor: "{colors.message-background}"
    textColor: "#285637"
    rounded: "{rounded.container}"
    padding: "16px"
---

# Design System: Quíbar

## Overview

**Creative North Star: "Quíbar como guía del territorio existente"**

Esta descripción conserva la identidad implementada: verdes profundos, superficies claras y la mascota suministrada. Es un registro del código actual, no una nueva dirección de marca. Las cifras del frontmatter corresponden a patrones reutilizados en la experiencia del mapa; la administración conserva sus variables globales.

**Key Characteristics:**
- Contraste entre panel blanco y cabecera verde de la guía.
- Controles táctiles y texto directo en español.
- Identificación visual distinta para comercios, atractivos y tótem.

## Colors

### Primary

El verde global identifica acciones administrativas y componentes compartidos. En el mapa, el verde de acción cubre botones y comercios; el verde profundo cubre la cabecera de la guía y sectores seleccionados.

### Secondary

Terracota identifica atractivos. Azul identifica el tótem; no representa otra categoría de comercio. El tono cálido de foco hace visible la navegación por teclado.

### Neutral

Fondos claros de matiz verde sostienen la aplicación, los mensajes y las listas. Blanco separa los controles y el panel de la superficie cartográfica; los bordes suaves dividen regiones y filas.

**The Geographic Identity Rule.** Mantener la correspondencia entre colores de marcadores y su leyenda; acompañar el color con forma o texto.

## Typography

Arial/Helvetica sostiene controles, descripciones y administración. El mapa usa controles de 13–14 px, nombres de lista de 16 px y descripciones de 14 px con interlineado de 1.65. Las estadísticas del recorrido usan cifras tabulares y un valor principal de 32 px.

Los encabezados existentes del panel usan Georgia: título de lugar de 30 px, guía y recorrido de 24 px. Esta dependencia de una tipografía de sistema para display se registra como deuda heredada, no como una nueva prescripción tipográfica. No se sustituyó durante esta extensión.

## Layout

El escritorio ocupa el alto de la ventana con cabecera de 88 px. El mapa toma el ancho restante junto a un panel de 386 px; este mide 430 px desde 1500 px y 340 px hasta 1050 px. El panel tiene desplazamiento propio y relleno habitual de 20 px por 22 px.

Hasta 750 px, mapa y panel pasan a una columna. El área cartográfica mide 59dvh con mínimo de 440 px; el panel sigue en el flujo y se desplaza con la página. Los avisos de mapa ausente preceden al lienzo cuando existen puntos, evitando tapar la ruta.

## Elevation & Depth

Bordes y cambios de superficie organizan paneles y filas. Sombras suaves separan controles superpuestos del mapa: búsqueda (`0 3px 10px #123f3510`), control de encuadre (`0 4px 16px #183c3420`) y teclado (`0 8px 36px #103c3435`). Las filas de lugares conservan fondo plano y borde inferior.

## Shapes

Controles y contenedores usan esquinas suaves. Los sectores tienen silueta de cápsula; los comercios usan marcadores de pin, los grupos círculos y los atractivos un rombo en la leyenda. La selección añade un contorno cálido separado del marcador.

## Components

- **Botones:** acciones principales verdes con texto blanco, ancho completo en el panel y altura táctil mínima de 44 px. Al pasar el puntero se oscurecen; deshabilitados bajan a media opacidad. El foco del mapa usa contorno de 3 px con separación de 3 px.
- **Filtros y navegación:** sectores con borde suave y selección verde sólida; tipos de lugar en una banda clara con pestaña seleccionada blanca. En móvil, “Todo el circuito” se abrevia visualmente a “Todos” conservando su nombre accesible.
- **Búsqueda:** campo blanco sin borde interior, contenedor redondeado, icono y botón de borrado. El teclado táctil aparece sobre el contenido y permite cerrarse.
- **Lugares:** filas separadas por líneas, icono sobre fondo tonal, nombre antes de categoría y sector. Los ejemplos ficticios y las ubicaciones pendientes llevan texto explícito.
- **Mensajes y sugerencias:** narración sobre verde claro; acciones para añadir paradas sobre crema. El nombre precede a los metadatos. La mascota original se muestra sin recortes en la cabecera de la guía.
- **Administración:** formularios blancos con borde y esquinas suaves, botones primarios del verde global y campos con etiqueta visible. Reutilizar estos patrones al ampliar sus pantallas.

## Do's and Don'ts

### Do:

- **Do** conservar la mascota suministrada y la identidad verde existente.
- **Do** mantener nombres y estados comprensibles junto a los símbolos del mapa.
- **Do** conservar foco visible y controles táctiles amplios.
- **Do** usar separadores y cambios de fondo para ordenar el panel.

### Don't:

- **Don't** comunicar categoría, selección o estado únicamente mediante color.
- **Don't** ocultar los avisos de datos ficticios o ubicación pendiente.
- **Don't** añadir movimiento que ignore la preferencia de movimiento reducido.
