import { Opening } from "./sections/Opening";
import { Analogy } from "./sections/Analogy";
import { Argument } from "./sections/Argument";
import { Composition } from "./sections/Composition";
import { Personae } from "./sections/Personae";
import { Authority } from "./sections/Authority";
import { Memory } from "./sections/Memory";
import { MetaSkill } from "./sections/MetaSkill";
import { Observatory } from "./sections/Observatory";
import { Closing } from "./sections/Closing";
import { TopBar } from "./components/TopBar";
import { ConstellationPage } from "./pages/ConstellationPage";
import { EntitiesPage } from "./pages/EntitiesPage";
import { AccountsPage } from "./pages/AccountsPage";
import { FunctionsPage } from "./pages/FunctionsPage";
import { OrgClonePage } from "./pages/OrgClonePage";
import { WorkflowRunPage } from "./pages/WorkflowRunPage";

export default function App() {
  // Standalone full-screen page views, addressable via ?view=...
  // Re-added after the entity-graph-coherence merge (Phase 2/3 added
  // AccountsPage + extended EntitiesPage; main's 71f48b96 had removed
  // the routing primitive). Replace with React Router when convenient.
  //
  // Gated to localhost only: every ?view=... page fetches from the
  // FastAPI control plane (/api/...), which doesn't exist in the
  // statically-hosted GitHub Pages bundle. In production we silently
  // fall through to the essay so a curious LinkedIn reader poking at
  // ?view=constellation doesn't land on a perpetually-loading shell.
  // We gate by hostname (not DEV) so the production-built bundle
  // served via `vite preview` on localhost still routes correctly —
  // that's the path boot-demo.sh uses for live operator demos.
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    const isLocal = host === "localhost" || host === "127.0.0.1" || host.endsWith(".local");
    // Azure Container Apps replay deploy also serves the operator
    // surface (NOT the essay). Allow ?view=* routes through there so
    // visitors can reach the Constellation, Entities, Workflow detail
    // pages on the public replay FQDN.
    const isContainerApps = host.endsWith(".azurecontainerapps.io");
    if (isLocal || isContainerApps || import.meta.env.DEV) {
      const params = new URLSearchParams(window.location.search);
      const view = params.get("view");
      if (view === "constellation") return <ConstellationPage />;
      if (view === "entities")      return <EntitiesPage />;
      if (view === "accounts")      return <AccountsPage />;
      if (view === "functions")     return <FunctionsPage />;
      if (view === "org-clone")     return <OrgClonePage />;
      if (view === "run")           return <WorkflowRunPage />;
    }
  }

  return (
    <div className="page">
      <TopBar />
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
      <Memory />
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
        {" and "}
        <a
          href="https://github.com/github/copilot-sdk"
          target="_blank"
          rel="noopener noreferrer"
          className="footer__link"
        >
          GitHub Copilot SDK
        </a>
        {". Source: "}
        <a
          href="https://github.com/arturcrmbot/zava-control-plane"
          target="_blank"
          rel="noopener noreferrer"
          className="footer__link"
        >
          zava-control-plane
        </a>
        {" · "}
        <a
          href="https://github.com/arturcrmbot/zava-design-skills"
          target="_blank"
          rel="noopener noreferrer"
          className="footer__link"
        >
          zava-design-skills
        </a>
        {" · "}
        <a
          href="https://aiappsgbb.github.io/zava-constellation/"
          target="_blank"
          rel="noopener noreferrer"
          className="footer__link"
        >
          zava-constellation
        </a>
        {" · 2026"}
      </footer>
    </div>
  );
}
