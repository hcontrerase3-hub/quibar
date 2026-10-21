# Product

## Platform
Web application for a shared touchscreen kiosk; responsive browser access for development and administration.

## Users and purpose
Visitors explore the Santa Bárbara–Huequecura–Ralco circuit, choose verified businesses and attractions, plan walking or driving directions from the kiosk, and discover optional stops along the actual road route. Staff curate and approve local content.

## Stack and operation
React/Vite/TypeScript, FastAPI, SQLAlchemy/Alembic, SQLite, Leaflet raster MBTiles, Valhalla local routing, optional Piper speech, Ollama locally or in the client's private datacenter. Docker packages application dependencies. Map, roads, and approved content must be prepared before field use.

## Constraints
Never invent locations, access, opening status or business facts. Preserve existing data, approval, CSRF and private administration. Suggestions appear automatically; stops require confirmation. Audio requires a visitor action. QR opens Google Maps, which recalculates the route. Return to initial map after 60 seconds of inactivity.

## Brand
Preserve Quíbar's supplied mascot, green/teal identity and approachable Spanish. The main public experience starts with the map, without a blocking welcome screen.
