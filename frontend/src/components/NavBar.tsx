import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { path: '/fields', label: 'Fields' },
  { path: '/ops', label: 'Control Room' },
  { path: '/sources', label: 'Sources' },
  { path: '/review', label: 'Review' },
  { path: '/leaderboard', label: 'Legacy Bench' },
  { path: '/scan', label: 'Artifact Scan' },
  { path: '/about', label: 'About' },
];

export default function NavBar() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-bg-primary/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/fields" className="flex items-center gap-2 no-underline">
          <span className="text-xl font-bold text-cyan-accent font-mono">AgentArena</span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden sm:flex flex-wrap justify-end gap-1">
          {NAV_ITEMS.map(({ path, label }) => {
            const active = location.pathname === path ||
              (path !== '/' && location.pathname.startsWith(path));
            return (
              <Link
                key={path}
                to={path}
                className={`rounded-md px-3 py-1.5 text-sm no-underline transition-colors ${
                  active
                    ? 'bg-cyan-glow text-cyan-accent'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                }`}
              >
                {label}
              </Link>
            );
          })}
        </div>

        {/* Mobile hamburger button */}
        <button
          type="button"
          className="sm:hidden flex flex-col justify-center gap-1.5 p-2 text-text-secondary hover:text-text-primary"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle navigation menu"
          aria-expanded={menuOpen}
        >
          <span className={`block h-0.5 w-5 bg-current transition-transform duration-200 ${menuOpen ? 'translate-y-2 rotate-45' : ''}`} />
          <span className={`block h-0.5 w-5 bg-current transition-opacity duration-200 ${menuOpen ? 'opacity-0' : ''}`} />
          <span className={`block h-0.5 w-5 bg-current transition-transform duration-200 ${menuOpen ? '-translate-y-2 -rotate-45' : ''}`} />
        </button>
      </div>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div className="sm:hidden border-t border-border px-4 pb-3">
          <div className="flex flex-col gap-1 pt-2">
            {NAV_ITEMS.map(({ path, label }) => {
              const active = location.pathname === path ||
                (path !== '/' && location.pathname.startsWith(path));
              return (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setMenuOpen(false)}
                  className={`rounded-md px-3 py-2 text-sm no-underline transition-colors ${
                    active
                      ? 'bg-cyan-glow text-cyan-accent'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </nav>
  );
}
