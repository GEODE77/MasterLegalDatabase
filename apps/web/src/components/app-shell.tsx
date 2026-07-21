import Link from "next/link";
import type { ReactNode } from "react";
import {
  Bell,
  Building2,
  FileSearch,
  GitBranch,
  Home,
  Landmark,
  Search,
  ShieldCheck,
  UserRound
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/search", label: "Search", icon: Search },
  { href: "/communities", label: "Communities", icon: Landmark },
  { href: "/dockets", label: "Dockets", icon: FileSearch },
  { href: "/agencies/CDPHE_AQCC", label: "Agencies", icon: Building2 },
  { href: "/timeline", label: "Timeline", icon: GitBranch },
  { href: "/issues", label: "Data Issues", icon: ShieldCheck },
  { href: "/profile", label: "Profile", icon: UserRound }
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <Link className="brand" href="/">
          <span className="brand-mark">
            <Landmark className="icon" aria-hidden="true" />
          </span>
          <span className="brand-name">
            <strong>Geode Commons</strong>
            <span>Source first</span>
          </span>
        </Link>

        <nav className="nav-group">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="nav-link">
              <item.icon aria-hidden="true" />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      <main className="shell-main">
        <header className="topbar">
          <form className="topbar-search" action="/search">
            <Search className="icon" aria-hidden="true" />
            <input
              className="search-input"
              name="q"
              placeholder="Search citations, agencies, rules, questions"
              type="search"
            />
          </form>
          <div className="button-row" aria-label="Account actions">
            <Link className="button" href="/review">
              <ShieldCheck className="icon" aria-hidden="true" />
              Review
            </Link>
            <Link className="user-chip" href="/profile">
              <span className="avatar">GC</span>
              <span>Research workspace</span>
            </Link>
            <Link className="button" href="/notifications" aria-label="Notifications">
              <Bell className="icon" aria-hidden="true" />
            </Link>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
