// web/client/main.tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import FleetControlShell from "./components/feed/FleetControlShell";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <FleetControlShell />
    </BrowserRouter>
  </React.StrictMode>,
);
