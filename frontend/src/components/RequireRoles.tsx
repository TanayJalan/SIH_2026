import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "./ui";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../lib/api";
import { ROLE_LABELS } from "../lib/roles";

export default function RequireRoles({
  roles,
  children,
}: {
  roles: Role[];
  children: ReactNode;
}) {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  if (!roles.includes(user.role)) {
    return (
      <section className="mx-auto max-w-2xl rounded-panel border border-breach bg-surface p-8 text-center">
        <p className="text-12 font-semibold uppercase tracking-[0.18em] text-breach-strong">
          Access denied
        </p>
        <h1 className="mt-3 font-serif text-28 font-semibold text-ink">
          This section is restricted
        </h1>
        <p className="mt-3 text-14 leading-5 text-ink-700">
          The {ROLE_LABELS[user.role].toLowerCase()} role does not have permission to view this
          page. Use the navigation menu to continue with an available task.
        </p>
        <Button asChild className="mt-6">
          <Link to="/">Return to overview</Link>
        </Button>
      </section>
    );
  }

  return <>{children}</>;
}
