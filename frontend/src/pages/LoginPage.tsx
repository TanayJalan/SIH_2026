import { useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ChevronDown,
  Eye,
  EyeOff,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import CountUpNumber from "../components/CountUpNumber";
import { Button } from "../components/ui";
import { useAuth } from "../auth/AuthContext";
import FullPageLoader from "../components/FullPageLoader";
import {
  API_BASE_URL,
  ApiError,
  getPublicStats,
  type PublicDemoAccount,
  type PublicStats,
} from "../lib/api";
import { formatDate } from "../lib/format";

function destinationFromState(state: unknown): string {
  if (
    typeof state === "object" &&
    state !== null &&
    "from" in state &&
    typeof (state as { from: unknown }).from === "string"
  ) {
    const from = (state as { from: string }).from;
    if (from.startsWith("/") && !from.startsWith("//") && from !== "/login") {
      return from;
    }
  }
  return "/";
}

const integerFormatter = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 0,
});

const averageFormatter = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function formatInteger(value: number): string {
  return integerFormatter.format(Math.round(value));
}

function formatAverage(value: number): string {
  return averageFormatter.format(value);
}

interface StatValueProps {
  value: number | null;
  format: (value: number) => string;
  unavailableLabel?: string;
}

function StatValue({
  value,
  format,
  unavailableLabel = "Not available",
}: StatValueProps) {
  if (value === null) {
    return (
      <span className="font-serif text-40 leading-none text-ink-300">
        <span aria-hidden="true">—</span>
        <span className="sr-only">{unavailableLabel}</span>
      </span>
    );
  }

  return (
    <CountUpNumber
      value={value}
      format={format}
      className="font-serif text-40 leading-none tracking-[-0.02em] text-ink tabular-nums"
    />
  );
}

function TodayStrip({ stats }: { stats: PublicStats | undefined }) {
  return (
    <section aria-labelledby="today-heading" className="border-y border-ink/10">
      <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2 py-3.5">
        <h2
          id="today-heading"
          className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500"
        >
          <span className="size-1.5 rounded-pill bg-ok" aria-hidden="true" />
          Today · live
        </h2>
        <p className="text-12 text-ink-500">
          {stats ? formatDate(stats.as_of) : "Live snapshot"}
        </p>
      </div>

      <dl className="grid grid-cols-1 divide-y divide-ink/10 border-t border-ink/10 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <div className="py-5 sm:py-6 sm:pr-5">
          <dt className="max-w-[13rem] text-12 leading-5 text-ink-500">
            Applications in progress
          </dt>
          <dd className="mt-3">
            <StatValue value={stats?.applications_in_progress ?? null} format={formatInteger} />
          </dd>
        </div>
        <div className="py-5 sm:px-5 sm:py-6">
          <dt className="max-w-[13rem] text-12 leading-5 text-ink-500">
            Average days to decision
          </dt>
          <dd className="mt-3">
            <StatValue value={stats?.average_days_to_decision ?? null} format={formatAverage} />
          </dd>
        </div>
        <div className="py-5 sm:py-6 sm:pl-5">
          <dt className="max-w-[13rem] text-12 leading-5 text-ink-500">
            Institutions needing attention
          </dt>
          <dd className="mt-3">
            <StatValue
              value={stats?.institutions_needing_attention ?? null}
              format={formatInteger}
            />
          </dd>
        </div>
      </dl>
    </section>
  );
}

interface DemoAccountsProps {
  accounts: PublicDemoAccount[];
  onSelect: (account: PublicDemoAccount) => void;
}

function DemoAccounts({ accounts, onSelect }: DemoAccountsProps) {
  return (
    <details className="group mt-7 border-t border-line pt-5">
      <summary className="flex cursor-pointer list-none items-center gap-3 rounded-input py-2 text-13 font-medium text-ink-700 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface [&::-webkit-details-marker]:hidden">
        <span>Demo accounts</span>
        <span className="text-12 font-normal text-ink-500">Fill the form</span>
        <ChevronDown
          aria-hidden="true"
          className="ml-auto size-4 text-ink-500 transition-transform group-open:rotate-180 motion-reduce:transition-none"
        />
      </summary>
      <p className="mt-2 text-12 leading-5 text-ink-500">
        Select a role to fill the email and demo password. These entries are only shown when
        demo mode is enabled.
      </p>
      <ul className="mt-3 divide-y divide-line overflow-hidden rounded-input border border-line">
        {accounts.map((account) => (
          <li key={account.role}>
            <button
              type="button"
              onClick={() => onSelect(account)}
              aria-label={`Use ${account.label} demo account, ${account.email}`}
              className="flex w-full items-center gap-4 bg-surface px-3.5 py-3 text-left transition-colors hover:bg-paper focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
            >
              <span className="min-w-0">
                <span className="block text-13 font-medium text-ink">{account.label}</span>
                <span className="mt-0.5 block truncate text-12 text-ink-500">
                  {account.email}
                </span>
              </span>
              <span className="ml-auto shrink-0 text-12 font-medium text-ink-500">Use</span>
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}

export default function LoginPage() {
  const { user, isInitializing, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const emailRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const statsQuery = useQuery({
    queryKey: ["public-stats"],
    queryFn: getPublicStats,
    enabled: !user,
    staleTime: 60_000,
  });

  const destination = destinationFromState(location.state);

  if (isInitializing) {
    return <FullPageLoader label="Checking your session" />;
  }

  if (user) {
    return <Navigate to={destination} replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(destination, { replace: true });
    } catch (loginError) {
      setError(
        loginError instanceof ApiError
          ? loginError.message
          : "Sign in failed. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const fillDemoAccount = (account: PublicDemoAccount) => {
    setEmail(account.email);
    setPassword(account.password);
    setError(null);
    emailRef.current?.focus();
  };

  const stats = statsQuery.data;

  return (
    <div className="login-grid flex min-h-screen flex-col bg-paper">
      <main className="grid flex-1 grid-cols-1 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section className="flex min-h-[calc(100svh-5.5rem)] flex-col px-6 py-8 sm:px-10 lg:min-h-0 lg:px-14 lg:py-12 xl:px-20">
          <header className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-input border border-ink/15 bg-surface text-12 font-semibold tracking-[0.16em] text-ink">
              AI
            </span>
            <div>
              <p className="text-14 font-semibold text-ink">AICTE Approval Workflow</p>
              <p className="mt-0.5 text-12 text-ink-500">Technical institution approvals</p>
            </div>
          </header>

          <div className="mt-16 max-w-[48rem] lg:mt-[clamp(4rem,11vh,8rem)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-500">
              A single accountable flow
            </p>
            <h1 className="mt-5 text-balance font-serif text-[clamp(2.65rem,5.1vw,4.9rem)] font-semibold leading-[0.98] tracking-[-0.035em] text-ink">
              Every approval, on time and on record.
            </h1>
            <p className="mt-6 max-w-[37rem] text-16 leading-7 text-ink-700">
              A calm, auditable path for New and Extension applications — from institutional
              submission through scrutiny and inspection to a recorded decision.
            </p>
          </div>

          <div className="mt-16 pt-14 lg:mt-auto lg:pt-20">
            <TodayStrip stats={stats} />
            {statsQuery.isError ? (
              <p className="mt-3 text-12 text-ink-500">
                Live figures are temporarily unavailable.
              </p>
            ) : null}
          </div>
        </section>

        <section className="flex items-center justify-center border-t border-line bg-surface px-6 py-10 sm:px-10 lg:border-l lg:border-t-0 lg:px-12">
          <div className="w-full max-w-[27rem]">
            <div>
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500">
                <ShieldCheck aria-hidden="true" className="size-3.5" />
                Secure access
              </p>
              <h2 className="mt-3 font-serif text-28 font-semibold tracking-[-0.015em] text-ink">
                Sign in to your workspace
              </h2>
              <p className="mt-2 text-13 leading-5 text-ink-500">
                Use the account issued for your role in the approval workflow.
              </p>
            </div>

            <form className="mt-8" onSubmit={handleSubmit}>
              <div>
                <label htmlFor="email" className="block text-13 font-medium text-ink-700">
                  Email address
                </label>
                <input
                  ref={emailRef}
                  id="email"
                  name="email"
                  type="email"
                  required
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  autoFocus
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? "login-error" : undefined}
                  className="mt-2 h-11 w-full rounded-input border border-line bg-surface px-3.5 text-14 text-ink transition-colors placeholder:text-ink-300 hover:border-ink-300 focus-visible:border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/25"
                  placeholder="name@example.edu"
                />
              </div>

              <div className="mt-5">
                <label htmlFor="password" className="block text-13 font-medium text-ink-700">
                  Password
                </label>
                <div className="relative mt-2">
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={error ? "login-error" : undefined}
                    className="h-11 w-full rounded-input border border-line bg-surface pl-3.5 pr-12 text-14 text-ink transition-colors placeholder:text-ink-300 hover:border-ink-300 focus-visible:border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/25"
                    placeholder="Enter your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((visible) => !visible)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-input text-ink-500 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
                  >
                    {showPassword ? (
                      <EyeOff aria-hidden="true" className="size-4" />
                    ) : (
                      <Eye aria-hidden="true" className="size-4" />
                    )}
                  </button>
                </div>
              </div>

              <div
                id="login-error"
                role="alert"
                aria-live="assertive"
                aria-atomic="true"
                className="mt-4 min-h-11"
              >
                {error ? (
                  <p className="rounded-input border border-breach bg-breach-soft px-3.5 py-2.5 text-13 leading-5 text-breach-strong">
                    {error}
                  </p>
                ) : null}
              </div>

              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={isSubmitting}
                aria-busy={isSubmitting}
              >
                {isSubmitting ? (
                  <LoaderCircle
                    aria-hidden="true"
                    className="size-4 motion-safe:animate-spin"
                  />
                ) : null}
                {isSubmitting ? "Signing in…" : "Sign in"}
              </Button>
            </form>

            {stats?.demo_mode && stats.demo_accounts.length > 0 ? (
              <DemoAccounts accounts={stats.demo_accounts} onSelect={fillDemoAccount} />
            ) : null}

            <p className="mt-7 text-12 leading-5 text-ink-500">
              Access is limited to authorised users. Every sign-in is recorded in the audit log.
            </p>
          </div>
        </section>
      </main>

      <footer className="relative border-t border-line bg-surface">
        <div className="flex flex-col gap-2 px-6 py-5 text-12 text-ink-500 sm:flex-row sm:items-center sm:gap-5 sm:px-10 lg:px-14 xl:px-20">
          <span className="font-medium text-ink">AICTE Approval Workflow</span>
          <span className="sm:border-l sm:border-line sm:pl-5">
            Prototype for Smart India Hackathon
          </span>
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 font-medium text-ink-700 underline-offset-4 hover:text-ink hover:underline sm:ml-auto"
          >
            API documentation
            <ArrowUpRight aria-hidden="true" className="size-3" />
          </a>
        </div>
      </footer>
    </div>
  );
}
