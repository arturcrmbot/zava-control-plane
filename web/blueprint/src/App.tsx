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

export default function App() {
  // Standalone full-screen constellation view, addressable via
  //   /?view=constellation
  // Bypasses the editorial page entirely so the visual lives on its own
  // and can be projected, recorded, or deployed independently.
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    if (params.get("view") === "constellation") {
      return <ConstellationPage />;
    }
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
