---
name: Quíbar · Colbún
description: Sistema visual de la interfaz táctil del mapa territorial y panel de administración de Quíbar.
colors:
  primary: "#0076A8"
  accent: "#00B2E6"
  secondary: "#3662B2"
  interest: "#C7520E"
  station: "#8BBB2F"
  focus: "#FF8031"
  highlight: "#FFCD00"
  background: "#F5F7FA"
  surface: "#FFFFFF"
  ink: "#2B3036"
  muted: "#55585A"
  border: "#DCE3EB"
  map-green: "#CFE3BC"
typography:
  display:
    fontFamily: "'Montserrat', 'Inter', 'Segoe UI', system-ui, -apple-system, Arial, Helvetica, sans-serif"
    headingWeight: 800
    bodyWeight: 500
    controlSize: "13px–14px"
rounded:
  control: "999px"
  container: "16px–20px"
  card: "12px"
spacing:
  compact: "8px"
  control: "12px"
  panel: "16px–18px"
---

# Design System: Quíbar (Identidad Colbún)

## Overview

**Creative North Star: "Mapa territorial a pantalla completa con explorador flotante retráctil Colbún"**

La interfaz pública del tótem prioriza el mapa interactivo del circuito Santa Bárbara–Huequecura–Ralco desde el primer fotograma, acompañado de un panel lateral flotante retráctil, controles HUD de alto contraste táctil y la mascota Quíbar. Tanto el tótem como la administración comparten los tokens `--colbun-*` definidos en `app/globals.css`.

## Colors

- **Primary (`--colbun-blue-deep: #0076A8`, `--colbun-blue: #00B2E6`, `--colbun-blue-secondary: #3662B2`)**: acciones principales, pines de comercios, trazado de rutas y navegación activa.
- **Interest (`--colbun-interest-pin: #C7520E`, `--colbun-orange: #FF8031`)**: atractivos turísticos (contraste ≥ 4.5:1 con icono blanco) y anillo de foco visible.
- **Station (`--colbun-green: #8BBB2F`)**: marcador de ubicación del tótem ("Usted está aquí") con pulso radar.
- **Highlight (`--colbun-yellow: #FFCD00`)**: selección y paradas sugeridas en el mapa.
- **Neutrals (`--background: #F5F7FA`, `--colbun-white: #FFFFFF`, `--colbun-ink: #2B3036`, `--colbun-muted: #55585A`, `--border: #DCE3EB`)**: superficies claras de alto contraste pensadas para pantallas táctiles bajo luz ambiental.

## Typography & Offline Resilience

La familia principal es `--font-display` (`Montserrat` con respaldo geométrico del sistema sin peticiones de red externas para garantizar operación 100 % offline en el tótem). Los números de distancia, duración y temperatura usan `font-variant-numeric: tabular-nums`.

## Layout & Responsive

- **Escritorio (`> 1280 px`)**: mapa a pantalla completa, barra HUD superior izquierda (buscador, *Lugares*, *Ver circuito*, *Centrar mapa* y filtros de sector), tarjeta de clima a la izquierda del panel flotante (`420 px`, `446 px` en `≥ 1500 px`), zoom en esquina inferior izquierda y pie `.map-footer` desplazado a su derecha (`left: 72px`).
- **Pantallas intermedias (`≤ 1280 px` / `≤ 1100 px`)**: la tarjeta de clima baja a `bottom: 64px` para no colisionar con el HUD; las etiquetas de botones secundarios pasan a solo icono en `≤ 1100 px`.
- **Móvil (`≤ 750 px`)**: mapa superior (`58dvh`, mínimo `420 px`) con clima compacto (icono + temperatura) y panel inferior en flujo normal.

## Motion & Accessibility

- **Objetivos táctiles**: mínimo `44×44 px` en todos los botones, pestañas, zoom y controles del teclado táctil.
- **WAI-ARIA**: `tablist`/`tab`/`tabpanel` vinculados con navegación por flechas, `inert` en panel colapsado y foco visible compatible con `forced-colors`.
- **Animaciones GPU (60/120 fps)**: inflado elástico en hover de burbujas (`linear()` spring + `cubic-bezier` fallback), pulso radar del tótem, trazado *draw-on* de rutas, clima animado según condición real y panel retráctil deslizante. Todo se detiene limpiamente bajo `prefers-reduced-motion: reduce` preservando realces visuales sin movimiento.
