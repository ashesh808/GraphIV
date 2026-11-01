"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "./icon";

export function SiteHeader() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.dataset.theme === "dark");
  }, []);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    try { localStorage.setItem("graphiv.theme", next ? "dark" : "light"); } catch { /* The theme still works without storage. */ }
  }

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href="/" className="brand" aria-label="GraphIV library">
          <span className="brand-mark" aria-hidden="true">G<span>·</span></span>
          <span>GraphIV</span>
        </Link>
        <span className="header-divider" aria-hidden="true" />
        <Link href="/" className="header-library">Library</Link>
        <div className="header-actions">
          <a href="https://github.com/ashesh808/GraphIV" className="source-link" target="_blank" rel="noreferrer">Project <Icon name="external" width="13" height="13" /></a>
          <span className="header-divider" aria-hidden="true" />
          <button className="icon-button theme-toggle" onClick={toggleTheme} aria-label={dark ? "Use light theme" : "Use dark theme"} title={dark ? "Use light theme" : "Use dark theme"}>
            <Icon name={dark ? "sun" : "moon"} width="18" height="18" />
          </button>
        </div>
      </div>
    </header>
  );
}
