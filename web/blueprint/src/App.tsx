import { Opening } from "./sections/Opening";
import { Analogy } from "./sections/Analogy";
import { Argument } from "./sections/Argument";
import { AgencyStory } from "./sections/AgencyStory";
import { Verticals } from "./sections/Verticals";
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
import { isRuntimeViewAllowed } from "./lib/runtimeViews";

export default function App() {
  // Standalone full-screen page views, addressable via ?view=...
  // Re-added after the entity-graph-coherence merge (Phase 2/3 added
  // AccountsPage + extended EntitiesPage; main's 71f48b96 had removed
  // the routing primitive). Replace with React Router when convenient.
  //
  // Routing is gated via isRuntimeViewAllowed: enabled for localhost,
  // *.azurecontainerapps.io, DEV, and any custom domain whose
  // VITE_DEMO_URL resolves to the same origin (covers the ACA Docker
  // bundle with VITE_DEMO_URL=/). Disabled for GitHub Pages where
  // VITE_DEMO_URL points at a different-origin ACA URL and the FastAPI
  // control plane (/api/...) is not reachable.
  if (typeof window !== "undefined") {
    if (
      isRuntimeViewAllowed(
        window.location.origin,
        import.meta.env.VITE_DEMO_URL,
        import.meta.env.DEV,
      )
    ) {
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
      <AgencyStory />
      <hr className="rule" />
      <Verticals />
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
        {" · August 2026"}
      </footer>
    </div>
  );
}
