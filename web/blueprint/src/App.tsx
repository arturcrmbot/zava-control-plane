import { Opening } from "./sections/Opening";
import { Analogy } from "./sections/Analogy";
import { Argument } from "./sections/Argument";
import { Composition } from "./sections/Composition";
import { MetaSkill } from "./sections/MetaSkill";
import { Observatory } from "./sections/Observatory";
import { Closing } from "./sections/Closing";

export default function App() {
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
