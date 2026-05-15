import { Opening } from "./sections/Opening";
import { Analogy } from "./sections/Analogy";
import { Argument } from "./sections/Argument";
import { Composition } from "./sections/Composition";
import { Personae } from "./sections/Personae";
import { Authority } from "./sections/Authority";
import { MetaSkill } from "./sections/MetaSkill";
import { Observatory } from "./sections/Observatory";
import { Closing } from "./sections/Closing";
import { ConstellationPage } from "./pages/ConstellationPage";
import { EntitiesPage } from "./pages/EntitiesPage";
import { AccountsPage } from "./pages/AccountsPage";
import { FunctionsPage } from "./pages/FunctionsPage";
import { OrgClonePage } from "./pages/OrgClonePage";

export default function App() {
  // Standalone full-screen page views, addressable via ?view=...
  // Re-added after the entity-graph-coherence merge (Phase 2/3 added
  // AccountsPage + extended EntitiesPage; main's 71f48b96 had removed
  // the routing primitive). Replace with React Router when convenient.
  //
  // Gated to dev builds only: every ?view=... page fetches from the
  // FastAPI control plane (/api/...), which doesn't exist in the
  // statically-hosted GitHub Pages bundle. In production we silently
  // fall through to the essay so a curious LinkedIn reader poking at
  // ?view=constellation doesn't land on a perpetually-loading shell.
  if (import.meta.env.DEV && typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const view = params.get("view");
    if (view === "constellation") return <ConstellationPage />;
    if (view === "entities")      return <EntitiesPage />;
    if (view === "accounts")      return <AccountsPage />;
    if (view === "functions")     return <FunctionsPage />;
    if (view === "org-clone")     return <OrgClonePage />;
  }

  return (
    <div className="page">
      <Opening />
      <hr className="rule" />
      <Analogy />
      <hr className="rule" />
      <Argument />
      <hr className="rule" />
      <Composition />
      <hr className="rule" />
      <Personae />
      <hr className="rule" />
      <Authority />
      <hr className="rule" />
      <MetaSkill />
      <hr className="rule" />
      <Observatory />
      <hr className="rule" />
      <Closing />
      <footer className="footer">
        Written by{" "}
        <a
          href="https://uk.linkedin.com/in/arturzielinski"
          target="_blank"
          rel="noopener noreferrer"
          className="footer__link"
        >
          Artur Zielinski
        </a>
        {" · 2026"}
      </footer>
    </div>
  );
}
