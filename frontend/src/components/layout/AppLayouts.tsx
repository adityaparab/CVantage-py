import type { ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { ThemeToggle } from "@/components/ui";
import { cn } from "@/lib/cn";

function Brand() {
  return (
    <Link to="/" className="text-lg font-bold text-text">
      CV<span className="text-accent-text">antage</span>
    </Link>
  );
}

function NavItem({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent",
          isActive ? "bg-accent-soft text-accent-text" : "text-muted hover:text-text",
        )
      }
    >
      {children}
    </NavLink>
  );
}

function TopBar({ children }: { children?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-card/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Brand />
          <nav className="hidden items-center gap-1 sm:flex">{children}</nav>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

export function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Brand />
          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="rounded-md px-3 py-2 text-sm font-medium text-muted hover:text-text"
            >
              Log in
            </Link>
            <Link
              to="/register"
              className="rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Sign up
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}

export function CandidateLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <TopBar>
        <NavItem to="/dashboard">Dashboard</NavItem>
      </TopBar>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}

export function AdminLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <TopBar>
        <NavItem to="/admin">Dashboard</NavItem>
        <NavItem to="/admin/users">Users</NavItem>
        <NavItem to="/admin/settings">Settings</NavItem>
      </TopBar>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
