import type { Role } from "./api";

export type NavIcon =
  | "overview"
  | "applications"
  | "compliance"
  | "alerts"
  | "alert-rules"
  | "audit"
  | "profile";

export interface NavItem {
  label: string;
  to: string;
  end?: boolean;
  icon: NavIcon;
  shortcut?: string;
}

export const ROLE_LABELS: Record<Role, string> = {
  INSTITUTION_ADMIN: "Institution administrator",
  SCRUTINY_OFFICER: "Scrutiny officer",
  INSPECTION_COMMITTEE: "Inspection committee",
  REGIONAL_HEAD: "Regional head",
  SUPER_ADMIN: "Super administrator",
};

export const ROLE_SCOPE_DESCRIPTIONS: Record<Role, string> = {
  INSTITUTION_ADMIN:
    "You can view applications submitted by your own institution only.",
  SCRUTINY_OFFICER:
    "You can view applications assigned to you or submitted in your region.",
  INSPECTION_COMMITTEE:
    "You can view applications with an inspection assigned to you.",
  REGIONAL_HEAD:
    "You can view applications and audit records for institutions in your region.",
  SUPER_ADMIN: "You can view all applications and audit records in the system.",
};

const ROLE_NAV: Record<Role, NavItem[]> = {
  INSTITUTION_ADMIN: [
    { label: "Overview", to: "/", end: true, icon: "overview", shortcut: "g d" },
    {
      label: "My applications",
      to: "/applications",
      icon: "applications",
      shortcut: "g a",
    },
    { label: "Alerts", to: "/alerts", icon: "alerts", shortcut: "g l" },
  ],
  SCRUTINY_OFFICER: [
    { label: "Overview", to: "/", end: true, icon: "overview", shortcut: "g d" },
    {
      label: "Scrutiny queue",
      to: "/applications",
      icon: "applications",
      shortcut: "g a",
    },
    { label: "Alerts", to: "/alerts", icon: "alerts", shortcut: "g l" },
  ],
  INSPECTION_COMMITTEE: [
    { label: "Overview", to: "/", end: true, icon: "overview", shortcut: "g d" },
    {
      label: "Assigned inspections",
      to: "/applications",
      icon: "applications",
      shortcut: "g a",
    },
    { label: "Alerts", to: "/alerts", icon: "alerts", shortcut: "g l" },
  ],
  REGIONAL_HEAD: [
    { label: "Overview", to: "/", end: true, icon: "overview", shortcut: "g d" },
    {
      label: "Regional applications",
      to: "/applications",
      icon: "applications",
      shortcut: "g a",
    },
    {
      label: "Compliance",
      to: "/compliance",
      icon: "compliance",
      shortcut: "g c",
    },
    { label: "Alerts", to: "/alerts", icon: "alerts", shortcut: "g l" },
    {
      label: "Audit logs",
      to: "/audit-logs",
      icon: "audit",
      shortcut: "g u",
    },
  ],
  SUPER_ADMIN: [
    { label: "Overview", to: "/", end: true, icon: "overview", shortcut: "g d" },
    {
      label: "All applications",
      to: "/applications",
      icon: "applications",
      shortcut: "g a",
    },
    {
      label: "Compliance",
      to: "/compliance",
      icon: "compliance",
      shortcut: "g c",
    },
    { label: "Alerts", to: "/alerts", icon: "alerts", shortcut: "g l" },
    {
      label: "Alert rules",
      to: "/alert-rules",
      icon: "alert-rules",
      shortcut: "g r",
    },
    {
      label: "Audit logs",
      to: "/audit-logs",
      icon: "audit",
      shortcut: "g u",
    },
  ],
};

export const AUDIT_LOG_ROLES: Role[] = ["SUPER_ADMIN", "REGIONAL_HEAD"];

export function navItemsFor(role: Role): NavItem[] {
  return [
    ...ROLE_NAV[role],
    {
      label: "My profile",
      to: "/profile",
      icon: "profile",
      shortcut: "g p",
    },
  ];
}

export function applicationsLabelFor(role: Role): string {
  return ROLE_NAV[role].find((item) => item.to === "/applications")?.label ?? "Applications";
}
