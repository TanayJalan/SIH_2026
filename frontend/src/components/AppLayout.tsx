import { useEffect, useRef, useState } from "react";
import {
  Bell,
  BellRing,
  ChevronDown,
  FileText,
  Keyboard,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  Search,
  ShieldCheck,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import CommandPalette from "./CommandPalette";
import DemoTimeControl from "./DemoTimeControl";
import KeyboardShortcutsDialog from "./KeyboardShortcutsDialog";
import NotificationBell from "./NotificationBell";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerTitle,
  Tooltip,
} from "./ui";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../lib/api";
import { initials } from "../lib/format";
import {
  ROLE_LABELS,
  navItemsFor,
  type NavIcon,
} from "../lib/roles";
import { useAlertStream } from "../lib/useAlertStream";
import { cn } from "../lib/utils";

const NAV_ICONS: Record<NavIcon, LucideIcon> = {
  overview: LayoutDashboard,
  applications: FileText,
  compliance: ShieldCheck,
  alerts: Bell,
  "alert-rules": BellRing,
  audit: ScrollText,
  profile: UserRound,
};

const COLLAPSE_KEY = "aicte.nav_collapsed";
const SHORTCUT_WINDOW_MS = 1_200;

function SidebarNavigation({
  role,
  collapsed,
  onNavigate,
}: {
  role: Role;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const items = navItemsFor(role);

  return (
    <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-2 py-4">
      {!collapsed ? (
        <p className="px-2 pb-2 text-12 font-semibold uppercase tracking-[0.14em] text-ink-500">
          {ROLE_LABELS[role]}
        </p>
      ) : null}
      <ul className="space-y-0.5">
        {items.map((item) => {
          const Icon = NAV_ICONS[item.icon];
          const link = (
            <NavLink
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              aria-label={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  "group relative flex h-10 items-center gap-3 rounded-input text-13 transition-colors",
                  collapsed ? "justify-center px-2" : "px-3",
                  isActive
                    ? "font-semibold text-ink"
                    : "font-medium text-ink-700 hover:bg-paper hover:text-ink",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute inset-y-2 left-0 w-0.5 rounded-pill bg-ink transition-opacity",
                      isActive ? "opacity-100" : "opacity-0",
                    )}
                  />
                  <Icon
                    aria-hidden="true"
                    className={cn(
                      "size-4 shrink-0",
                      isActive ? "text-ink" : "text-ink-500 group-hover:text-ink-700",
                    )}
                  />
                  {!collapsed ? (
                    <>
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {item.shortcut ? (
                        <kbd className="shrink-0 rounded-input border border-line px-1.5 py-0.5 text-12 font-normal text-ink-300 transition-colors group-hover:text-ink-500">
                          {item.shortcut}
                        </kbd>
                      ) : null}
                    </>
                  ) : null}
                </>
              )}
            </NavLink>
          );

          return (
            <li key={item.to}>
              {collapsed ? (
                <Tooltip content={item.label} side="right">
                  {link}
                </Tooltip>
              ) : (
                link
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function SidebarBrand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link
      to="/"
      className={cn(
        "flex h-16 shrink-0 items-center border-b border-line",
        collapsed ? "justify-center px-3" : "gap-3 px-5 pr-12",
      )}
      aria-label="AICTE Approval Workflow home"
    >
      <span className="grid size-9 shrink-0 place-items-center rounded-input border border-ink bg-ink text-13 font-semibold tracking-wide text-surface">
        AI
      </span>
      {!collapsed ? (
        <span className="min-w-0">
          <span className="block truncate text-14 font-semibold text-ink">AICTE Approval</span>
          <span className="block truncate text-12 text-ink-500">Workflow portal</span>
        </span>
      ) : null}
    </Link>
  );
}

function SidebarPanel({
  role,
  collapsed,
  onToggle,
  onNavigate,
}: {
  role: Role;
  collapsed: boolean;
  onToggle?: () => void;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-surface">
      <SidebarBrand collapsed={collapsed} />
      <SidebarNavigation role={role} collapsed={collapsed} onNavigate={onNavigate} />
      <div className="border-t border-line p-2">
        {onToggle ? (
          <button
            type="button"
            onClick={onToggle}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            aria-pressed={collapsed}
            className={cn(
              "flex h-9 w-full items-center rounded-input text-13 font-medium text-ink-700 transition-colors hover:bg-paper hover:text-ink",
              collapsed ? "justify-center px-2" : "gap-2 px-3",
            )}
          >
            {collapsed ? (
              <PanelLeftOpen aria-hidden="true" className="size-4" />
            ) : (
              <>
                <PanelLeftClose aria-hidden="true" className="size-4" />
                <span>Collapse navigation</span>
              </>
            )}
          </button>
        ) : null}
        {!collapsed ? (
          <p className="mt-2 px-2 text-12 leading-4 text-ink-500">
            Illustrative Smart India Hackathon prototype. Sample institutions are fictional.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.isContentEditable ||
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT"
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  useAlertStream();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(
    () => window.localStorage.getItem(COLLAPSE_KEY) === "true",
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const pendingShortcut = useRef<{ key: string; at: number } | null>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.localStorage.setItem(COLLAPSE_KEY, String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    setMobileOpen(false);
    setUserMenuOpen(false);
    pendingShortcut.current = null;
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!userMenuOpen) {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      if (!userMenuRef.current?.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [userMenuOpen]);

  useEffect(() => {
    if (!user) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) {
        return;
      }

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setShortcutsOpen(false);
        setUserMenuOpen(false);
        setMobileOpen(false);
        setPaletteOpen((current) => !current);
        return;
      }

      if (isEditableTarget(event.target)) {
        return;
      }

      if (event.key === "?" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        if (!paletteOpen) {
          event.preventDefault();
          setUserMenuOpen(false);
          setMobileOpen(false);
          setShortcutsOpen(true);
        }
        return;
      }

      if (
        paletteOpen ||
        shortcutsOpen ||
        mobileOpen ||
        userMenuOpen ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        event.repeat
      ) {
        return;
      }

      const key = event.key.toLowerCase();
      const pending = pendingShortcut.current;
      if (pending && Date.now() - pending.at <= SHORTCUT_WINDOW_MS) {
        pendingShortcut.current = null;
        const destination = navItemsFor(user.role).find(
          (item) => item.shortcut === `g ${key}`,
        );
        if (destination) {
          event.preventDefault();
          navigate(destination.to);
        }
        return;
      }

      if (key === "g") {
        pendingShortcut.current = { key, at: Date.now() };
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen, navigate, paletteOpen, shortcutsOpen, user, userMenuOpen]);

  if (!user) {
    return null;
  }

  const handleSignOut = () => {
    setUserMenuOpen(false);
    logout();
    navigate("/login", { replace: true });
  };

  const showShortcuts = () => {
    setUserMenuOpen(false);
    setShortcutsOpen(true);
  };

  const roleLabel = ROLE_LABELS[user.role];

  return (
    <div className="min-h-screen bg-paper text-ink">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-input bg-surface px-4 py-2 text-14 font-medium text-ink shadow-popover focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden border-r border-line bg-surface transition-[width] duration-200 lg:flex lg:flex-col",
          collapsed ? "w-16" : "w-60",
        )}
        aria-label="Sidebar"
      >
        <SidebarPanel
          role={user.role}
          collapsed={collapsed}
          onToggle={() => setCollapsed((current) => !current)}
        />
      </aside>

      <Drawer open={mobileOpen} onOpenChange={setMobileOpen}>
        <DrawerContent
          id="mobile-navigation"
          side="left"
          className="w-72 max-w-[85vw] p-0"
        >
          <DrawerTitle className="sr-only">Navigation</DrawerTitle>
          <DrawerDescription className="sr-only">
            Primary navigation for your role.
          </DrawerDescription>
          <SidebarPanel
            role={user.role}
            collapsed={false}
            onNavigate={() => setMobileOpen(false)}
          />
        </DrawerContent>
      </Drawer>

      <div
        className={cn(
          "flex min-h-screen min-w-0 flex-col transition-[padding] duration-200",
          collapsed ? "lg:pl-16" : "lg:pl-60",
        )}
      >
        <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
          <div className="flex h-16 min-w-0 items-center gap-2 px-3 sm:px-5 lg:px-8">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="inline-flex size-9 shrink-0 items-center justify-center rounded-input text-ink-700 transition-colors hover:bg-paper hover:text-ink lg:hidden"
              aria-label="Open navigation"
              aria-expanded={mobileOpen}
              aria-controls="mobile-navigation"
            >
              <Menu aria-hidden="true" className="size-5" />
            </button>

            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="group flex h-9 w-9 min-w-0 shrink-0 items-center justify-center gap-2 rounded-input border border-line bg-paper text-left text-13 text-ink-500 transition-colors hover:border-ink-300 hover:bg-surface hover:text-ink-700 sm:w-auto sm:max-w-sm sm:flex-1 sm:justify-start sm:px-3"
              aria-label="Search applications, institutions and pages"
            >
              <Search aria-hidden="true" className="size-4 shrink-0" />
              <span className="hidden min-w-0 flex-1 truncate md:inline">
                Search applications…
              </span>
              <kbd className="ml-auto hidden shrink-0 rounded-input border border-line bg-surface px-1.5 py-0.5 text-12 text-ink-500 md:inline-flex">
                ⌘K
              </kbd>
            </button>

            <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-2">
              <DemoTimeControl />

              <NotificationBell />

              <span className="hidden max-w-36 truncate rounded-pill border border-line bg-paper px-2.5 py-1 text-12 font-medium text-ink-700 lg:inline-flex">
                {roleLabel}
              </span>

              <div ref={userMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setUserMenuOpen((current) => !current)}
                  aria-haspopup="menu"
                  aria-expanded={userMenuOpen}
                  aria-label="Open account menu"
                  className="flex h-9 items-center gap-1.5 rounded-input pl-0.5 pr-1 transition-colors hover:bg-paper"
                >
                  <span className="grid size-8 place-items-center rounded-pill bg-ink text-12 font-semibold text-surface">
                    {initials(user.name)}
                  </span>
                  <ChevronDown
                    aria-hidden="true"
                    className={cn(
                      "hidden size-3.5 text-ink-500 transition-transform sm:block",
                      userMenuOpen && "rotate-180",
                    )}
                  />
                </button>

                {userMenuOpen ? (
                  <div
                    role="menu"
                    aria-label="Account menu"
                    className="absolute right-0 top-full z-50 mt-2 w-64 rounded-panel border border-line bg-surface p-2 shadow-popover"
                  >
                    <div className="border-b border-line px-2.5 pb-2.5 pt-1.5">
                      <p className="truncate text-14 font-semibold text-ink">{user.name}</p>
                      <p className="mt-0.5 truncate text-12 text-ink-500">{user.email}</p>
                      <p className="mt-2 inline-flex rounded-pill bg-paper px-2 py-0.5 text-12 font-medium text-ink-700">
                        {roleLabel}
                      </p>
                    </div>
                    <div className="mt-1 space-y-0.5">
                      <Link
                        to="/profile"
                        role="menuitem"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex items-center gap-2 rounded-input px-2.5 py-2 text-13 text-ink transition-colors hover:bg-paper"
                      >
                        <UserRound aria-hidden="true" className="size-4 text-ink-500" />
                        My profile
                      </Link>
                      <button
                        type="button"
                        role="menuitem"
                        onClick={showShortcuts}
                        className="flex w-full items-center gap-2 rounded-input px-2.5 py-2 text-left text-13 text-ink transition-colors hover:bg-paper"
                      >
                        <Keyboard aria-hidden="true" className="size-4 text-ink-500" />
                        Keyboard shortcuts
                        <kbd className="ml-auto rounded-input border border-line px-1.5 text-12 text-ink-500">
                          ?
                        </kbd>
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        onClick={handleSignOut}
                        className="flex w-full items-center gap-2 rounded-input px-2.5 py-2 text-left text-13 text-breach-strong transition-colors hover:bg-breach-soft"
                      >
                        <LogOut aria-hidden="true" className="size-4" />
                        Sign out
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </header>

        <main
          id="main-content"
          className="mx-auto w-full min-w-0 max-w-[1280px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-10"
        >
          <Outlet />
        </main>

        <footer className="border-t border-line bg-surface px-4 py-5 text-center text-12 leading-5 text-ink-500 sm:px-6 lg:px-8">
          Illustrative Smart India Hackathon prototype. All sample institutions are fictional.
          Compliance thresholds and SLA values must be verified against the current AICTE Approval
          Process Handbook.
        </footer>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      <KeyboardShortcutsDialog
        open={shortcutsOpen}
        onOpenChange={setShortcutsOpen}
        role={user.role}
      />
    </div>
  );
}
