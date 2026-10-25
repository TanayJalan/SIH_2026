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
  REGULATION_BUREAU_OFFICER: "Regulation Bureau officer",
  SCRUTINY_COMMITTEE_MEMBER: "Scrutiny Committee member",
  EVC_MEMBER: "Expert Visit Committee member",
  REGIONAL_OFFICER: "Regional Officer",
  SHC_MEMBER: "Standing Hearing Committee member",
  SAC_MEMBER: "Standing Appellate Committee member",
  EXECUTIVE_COMMITTEE_MEMBER: "Executive Committee member",
  COMPLAINT_SCRUTINY_MEMBER: "Standing Complaint Scrutiny Committee member",
  SUPER_ADMIN: "Super administrator",
};

export const ROLE_SCOPE_DESCRIPTIONS: Record<Role, string> = {
  INSTITUTION_ADMIN:
    "You can view applications submitted by your own institution only.",
  REGULATION_BUREAU_OFFICER:
    "You can view applications in scrutiny across regions and manage the APH process.",
  SCRUTINY_COMMITTEE_MEMBER:
    "You can view applications assigned to you or submitted in your region.",
  EVC_MEMBER:
    "You can view applications with an Expert Visit Committee inspection assigned to you.",
  REGIONAL_OFFICER:
    "You can view applications and audit records for institutions in your region.",
  SHC_MEMBER:
    "You can view cases referred to the Standing Hearing Committee.",
  SAC_MEMBER:
    "You can view appeals referred to the Standing Appellate Committee.",
  EXECUTIVE_COMMITTEE_MEMBER:
    "You can view cases referred to the Executive Committee for a final decision.",
  COMPLAINT_SCRUTINY_MEMBER:
    "You can view complaints referred to the Standing Complaint Scrutiny Committee.",
  SUPER_ADMIN: "You can view all applications and audit records in the system.",
};

const OVERVIEW: NavItem = {
  label: "Overview",
  to: "/",
  end: true,
  icon: "overview",
  shortcut: "g d",
};

const ALERTS: NavItem = {
  label: "Alerts",
  to: "/alerts",
  icon: "alerts",
  shortcut: "g l",
};

function applicationsItem(label: string): NavItem {
  return {
    label,
    to: "/applications",
    icon: "applications",
    shortcut: "g a",
  };
}

const COMPLIANCE: NavItem = {
  label: "Compliance",
  to: "/compliance",
  icon: "compliance",
  shortcut: "g c",
};

const AUDIT_LOGS: NavItem = {
  label: "Audit logs",
  to: "/audit-logs",
  icon: "audit",
  shortcut: "g u",
};

const ROLE_NAV: Record<Role, NavItem[]> = {
  INSTITUTION_ADMIN: [OVERVIEW, applicationsItem("My applications"), ALERTS],
  REGULATION_BUREAU_OFFICER: [
    OVERVIEW,
    applicationsItem("Scrutiny queue"),
    ALERTS,
    AUDIT_LOGS,
  ],
  SCRUTINY_COMMITTEE_MEMBER: [
    OVERVIEW,
    applicationsItem("Scrutiny queue"),
    ALERTS,
  ],
  EVC_MEMBER: [OVERVIEW, applicationsItem("Assigned inspections"), ALERTS],
  REGIONAL_OFFICER: [
    OVERVIEW,
    applicationsItem("Regional applications"),
    COMPLIANCE,
    ALERTS,
    AUDIT_LOGS,
  ],
  SHC_MEMBER: [OVERVIEW, applicationsItem("Hearing cases"), ALERTS],
  SAC_MEMBER: [OVERVIEW, applicationsItem("Appeal cases"), ALERTS],
  EXECUTIVE_COMMITTEE_MEMBER: [
    OVERVIEW,
    applicationsItem("Committee cases"),
    ALERTS,
  ],
  COMPLAINT_SCRUTINY_MEMBER: [
    OVERVIEW,
    applicationsItem("Complaint cases"),
    ALERTS,
  ],
  SUPER_ADMIN: [
    OVERVIEW,
    applicationsItem("All applications"),
    COMPLIANCE,
    ALERTS,
    {
      label: "Alert rules",
      to: "/alert-rules",
      icon: "alert-rules",
      shortcut: "g r",
    },
    AUDIT_LOGS,
  ],
};

export const AUDIT_LOG_ROLES: Role[] = [
  "SUPER_ADMIN",
  "REGIONAL_OFFICER",
  "REGULATION_BUREAU_OFFICER",
];

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
