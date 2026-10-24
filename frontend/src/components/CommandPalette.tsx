import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import {
  Building2,
  CalendarClock,
  FileText,
  History,
  LayoutDashboard,
  Search,
  ShieldAlert,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui";
import { useAuth } from "../auth/AuthContext";
import { search, type SearchApplicationResult, type SearchInstitutionResult } from "../lib/api";
import { humanizeEnum, shortId } from "../lib/format";
import {
  getRecentItems,
  rememberRecentItem,
  type RecentItem,
  type RecentItemType,
} from "../lib/recent";

const SEARCH_DEBOUNCE_MS = 150;

function itemTitle(value: string | null, id: string): string {
  return value ?? `Application ${shortId(id)}`;
}

function recentIcon(type: RecentItemType) {
  if (type === "application") {
    return FileText;
  }
  if (type === "institution") {
    return Building2;
  }
  return LayoutDashboard;
}

function ItemBody({
  icon,
  title,
  detail,
  meta,
}: {
  icon: ReactNode;
  title: string;
  detail?: string;
  meta?: string;
}) {
  return (
    <>
      <span className="grid size-8 shrink-0 place-items-center rounded-input bg-paper text-ink-500">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-14 font-medium text-ink">{title}</span>
        {detail ? <span className="mt-0.5 block truncate text-12 text-ink-500">{detail}</span> : null}
      </span>
      {meta ? (
        <span className="shrink-0 text-12 tabular-nums text-ink-500">{meta}</span>
      ) : null}
    </>
  );
}

const itemClassName =
  "flex cursor-default select-none items-center gap-3 rounded-input px-3 py-2.5 text-left text-ink outline-none data-[selected=true]:bg-paper data-[disabled=true]:pointer-events-none data-[disabled=true]:text-ink-300";

export default function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [recent, setRecent] = useState<RecentItem[]>([]);
  const userId = user?.id;

  useEffect(() => {
    if (!open || !userId) {
      return;
    }
    setQuery("");
    setDebouncedQuery("");
    setRecent(getRecentItems(userId));
  }, [open, userId]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timeout);
  }, [query]);

  const searchQuery = useQuery({
    queryKey: ["global-search", user?.id, debouncedQuery],
    queryFn: () => search(token ?? "", debouncedQuery),
    enabled: open && Boolean(token),
    staleTime: 15_000,
    retry: false,
  });

  const hasSearchText = query.trim().length > 0;
  const quickActionMatches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return !needle || "open overdue applications".includes(needle);
  }, [query]);

  const go = (to: string, recentItem?: RecentItem) => {
    if (recentItem && userId) {
      setRecent(rememberRecentItem(userId, recentItem));
    }
    onOpenChange(false);
    navigate(to);
  };

  const selectPage = (label: string, path: string) => {
    go(path, { type: "page", id: path, label, to: path });
  };

  const selectApplication = (application: SearchApplicationResult) => {
    const title = itemTitle(application.reference, application.id);
    go(`/applications/${application.id}`, {
      type: "application",
      id: application.id,
      label: title,
      detail: `${application.institution_name} · ${humanizeEnum(application.status)}`,
      to: `/applications/${application.id}`,
    });
  };

  const selectInstitution = (institution: SearchInstitutionResult) => {
    const to = `/applications?institution_id=${encodeURIComponent(
      institution.id,
    )}&institution=${encodeURIComponent(institution.name)}`;
    go(to, {
      type: "institution",
      id: institution.id,
      label: institution.name,
      detail: `${institution.state} · ${institution.region}`,
      to,
    });
  };

  const resultPages = searchQuery.data?.pages ?? [];
  const resultApplications = searchQuery.data?.applications ?? [];
  const resultInstitutions = searchQuery.data?.institutions ?? [];
  const showInitialState =
    !hasSearchText && !searchQuery.isPending && resultPages.length === 0;
  const showNoResults =
    hasSearchText &&
    !searchQuery.isPending &&
    resultPages.length === 0 &&
    resultApplications.length === 0 &&
    resultInstitutions.length === 0 &&
    !quickActionMatches;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl overflow-hidden p-0">
        <DialogTitle className="sr-only">Global search and commands</DialogTitle>
        <DialogDescription className="sr-only">
          Search applications, institutions and pages, or run a quick action.
        </DialogDescription>

        <Command
          shouldFilter={false}
          loop
          label="Global search and commands"
          className="flex max-h-[min(75dvh,36rem)] min-h-0 flex-col"
        >
          <div className="flex items-center gap-3 border-b border-line px-4 py-3.5 pr-14">
            <Search aria-hidden="true" className="size-4 shrink-0 text-ink-500" />
            <Command.Input
              autoFocus
              value={query}
              onValueChange={setQuery}
              maxLength={100}
              aria-label="Search applications, institutions and pages"
              placeholder="Search applications, institutions and pages…"
              className="h-6 min-w-0 flex-1 bg-transparent text-14 text-ink outline-none placeholder:text-ink-500"
            />
            <kbd className="hidden shrink-0 rounded-input border border-line bg-paper px-1.5 py-0.5 text-12 text-ink-500 sm:inline-flex">
              Esc
            </kbd>
          </div>

          <Command.List className="min-h-0 flex-1 overflow-y-auto p-2">
            {searchQuery.isFetching ? (
              <Command.Loading className="px-3 py-2 text-12 text-ink-500">
                Searching visible records…
              </Command.Loading>
            ) : null}

            {showNoResults || showInitialState ? (
              <Command.Empty className="px-4 py-12 text-center text-14 text-ink-500">
                {showNoResults
                  ? "No matching applications, institutions or pages."
                  : "Start typing to search, or choose a page."}
              </Command.Empty>
            ) : null}

            {!hasSearchText && recent.length > 0 ? (
              <Command.Group
                heading="Recent"
                className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-12 [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-ink-500"
              >
                {recent.map((item) => {
                  const Icon = recentIcon(item.type);
                  return (
                    <Command.Item
                      key={`${item.type}:${item.id}`}
                      value={`recent:${item.type}:${item.id}`}
                      onSelect={() => go(item.to, item)}
                      className={itemClassName}
                    >
                      <ItemBody
                        icon={<Icon aria-hidden="true" className="size-4" />}
                        title={item.label}
                        detail={item.detail}
                        meta={item.type === "page" ? "Page" : undefined}
                      />
                    </Command.Item>
                  );
                })}
              </Command.Group>
            ) : null}

            {quickActionMatches ? (
              <Command.Group
                heading="Quick actions"
                className="mt-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-12 [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-ink-500"
              >
                <Command.Item
                  value="quick:overdue-applications"
                  onSelect={() =>
                    go("/applications?overdue=1", {
                      type: "page",
                      id: "quick:overdue-applications",
                      label: "Overdue applications",
                      to: "/applications?overdue=1",
                    })
                  }
                  className={itemClassName}
                >
                  <ItemBody
                    icon={<CalendarClock aria-hidden="true" className="size-4" />}
                    title="Open overdue applications"
                    detail="Filter cases whose SLA due date has passed"
                    meta="Quick action"
                  />
                </Command.Item>
              </Command.Group>
            ) : null}

            {resultPages.length > 0 ? (
              <Command.Group
                heading="Pages"
                className="mt-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-12 [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-ink-500"
              >
                {resultPages.map((page) => (
                  <Command.Item
                    key={page.path}
                    value={`page:${page.path}`}
                    onSelect={() => selectPage(page.label, page.path)}
                    className={itemClassName}
                  >
                    <ItemBody
                      icon={<LayoutDashboard aria-hidden="true" className="size-4" />}
                      title={page.label}
                      detail={page.path}
                    />
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {resultApplications.length > 0 ? (
              <Command.Group
                heading="Applications"
                className="mt-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-12 [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-ink-500"
              >
                {resultApplications.map((application) => (
                  <Command.Item
                    key={application.id}
                    value={`application:${application.id}`}
                    onSelect={() => selectApplication(application)}
                    className={itemClassName}
                  >
                    <ItemBody
                      icon={<FileText aria-hidden="true" className="size-4" />}
                      title={itemTitle(application.reference, application.id)}
                      detail={`${application.institution_name} · ${application.academic_year}`}
                      meta={humanizeEnum(application.status)}
                    />
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {resultInstitutions.length > 0 ? (
              <Command.Group
                heading="Institutions"
                className="mt-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-12 [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-ink-500"
              >
                {resultInstitutions.map((institution) => (
                  <Command.Item
                    key={institution.id}
                    value={`institution:${institution.id}`}
                    onSelect={() => selectInstitution(institution)}
                    className={itemClassName}
                  >
                    <ItemBody
                      icon={<Building2 aria-hidden="true" className="size-4" />}
                      title={institution.name}
                      detail={`${institution.state} · ${institution.region}`}
                      meta="Institution"
                    />
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {searchQuery.isError ? (
              <p className="flex items-center gap-2 px-3 py-3 text-12 text-breach-strong">
                <ShieldAlert aria-hidden="true" className="size-4 shrink-0" />
                Search is unavailable. Check the API connection and try again.
              </p>
            ) : null}

            {!hasSearchText && resultPages.length === 0 && searchQuery.isPending ? (
              <div className="px-4 py-10 text-center text-14 text-ink-500">Loading pages…</div>
            ) : null}

            {!hasSearchText && recent.length === 0 ? (
              <div className="flex items-center gap-2 px-3 py-2 text-12 text-ink-500">
                <History aria-hidden="true" className="size-3.5" />
                Recent items appear here after you open them.
              </div>
            ) : null}
          </Command.List>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line bg-paper px-4 py-2.5 text-12 text-ink-500">
            <span>
              <kbd className="rounded-input border border-line bg-surface px-1.5 py-0.5">↑↓</kbd>{" "}
              Navigate
            </span>
            <span>
              <kbd className="rounded-input border border-line bg-surface px-1.5 py-0.5">↵</kbd>{" "}
              Open
            </span>
            <span className="ml-auto hidden sm:inline">
              <kbd className="rounded-input border border-line bg-surface px-1.5 py-0.5">⌘K</kbd>{" "}
              Toggle search
            </span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
