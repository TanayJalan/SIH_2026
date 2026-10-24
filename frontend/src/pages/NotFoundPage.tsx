import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function NotFoundPage() {
  const { user } = useAuth();

  const card = (
    <section className="w-full max-w-xl rounded-panel border border-line bg-surface p-8 text-center sm:p-10">
      <p className="text-12 font-semibold uppercase tracking-[0.2em] text-ink-500">404</p>
      <h1 className="mt-3 font-serif text-28 font-semibold text-ink">Page not found</h1>
      <p className="mt-3 text-14 leading-5 text-ink-700">
        This address is outside the current approval-flow prototype. Return to the portal to
        continue.
      </p>
      <Link
        to={user ? "/" : "/login"}
        className="mt-7 inline-flex h-9 items-center justify-center rounded-input bg-saffron px-4 text-13 font-semibold text-ink transition-colors hover:bg-saffron-hover"
      >
        {user ? "Back to overview" : "Go to sign in"}
      </Link>
      <p className="mt-6 border-t border-line pt-5 text-12 text-ink-500">
        AICTE Approval Workflow · Illustrative Smart India Hackathon prototype
      </p>
    </section>
  );

  if (user) {
    return <div className="flex min-h-[55vh] items-center justify-center">{card}</div>;
  }

  return <div className="grid min-h-screen place-items-center bg-paper px-5">{card}</div>;
}
