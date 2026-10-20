import React from "react";
import ReactDOM from "react-dom/client";
import Home from "./page";
import Admin from "./admin";
import "./globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>{window.location.pathname.startsWith("/admin") ? <Admin /> : <Home />}</React.StrictMode>,
);
