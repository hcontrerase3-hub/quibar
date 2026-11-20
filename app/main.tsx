import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/montserrat/400.css";
import "@fontsource/montserrat/500.css";
import "@fontsource/montserrat/600.css";
import "@fontsource/montserrat/700.css";
import "@fontsource/montserrat/800.css";
import Home from "./page";
const Admin = React.lazy(() => import("./admin"));
import "./globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><React.Suspense fallback={<p>Cargando Quíbar…</p>}>{window.location.pathname.startsWith("/admin") ? <Admin /> : <Home />}</React.Suspense></React.StrictMode>,
);
