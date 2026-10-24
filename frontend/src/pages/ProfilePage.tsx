import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/PageHeader";
import { initials } from "../lib/format";
import { ROLE_LABELS, ROLE_SCOPE_DESCRIPTIONS } from "../lib/roles";

export default function ProfilePage() {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <>
      <PageHeader
        eyebrow="Account"
        title="My profile"
        description="Identity and access scope associated with the current authenticated session."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <section className="min-w-0 rounded-panel border border-line bg-surface p-6">
          <div className="flex items-center gap-4">
            <span className="grid h-14 w-14 place-items-center rounded-pill bg-ink text-14 font-semibold text-surface">
              {initials(user.name)}
            </span>
            <div className="min-w-0">
              <h2 className="truncate font-serif text-20 font-semibold text-ink">{user.name}</h2>
              <p className="truncate text-13 text-ink-500">{user.email}</p>
            </div>
          </div>
          <dl className="mt-6 space-y-4 border-t border-line pt-5">
            <div>
              <dt className="text-12 font-medium text-ink-500">
                Role
              </dt>
              <dd className="mt-1 font-medium text-ink">{ROLE_LABELS[user.role]}</dd>
            </div>
            <div>
              <dt className="text-12 font-medium text-ink-500">
                Account status
              </dt>
              <dd className="mt-1 font-medium text-ok-strong">
                {user.is_active ? "Active" : "Inactive"}
              </dd>
            </div>
            <div>
              <dt className="text-12 font-medium text-ink-500">
                Region
              </dt>
              <dd className="mt-1 font-medium text-ink">{user.region ?? "System-wide"}</dd>
            </div>
          </dl>
        </section>

        <div className="min-w-0 space-y-6">
          <section className="min-w-0 rounded-panel border border-line bg-surface p-6">
            <h2 className="font-serif text-20 font-semibold text-ink">Access scope</h2>
            <p className="mt-2 text-13 leading-5 text-ink-700">
              {ROLE_SCOPE_DESCRIPTIONS[user.role]}
            </p>
            <p className="mt-4 border-t border-line pt-4 text-12 leading-5 text-ink-500">
              Every role is enforced by the API. Hiding a menu item in the browser is not treated as
              an access control measure.
            </p>
          </section>

          <section className="min-w-0 rounded-panel border border-line bg-surface p-6">
            <h2 className="font-serif text-20 font-semibold text-ink">Institution</h2>
            {user.institution ? (
              <dl className="mt-4 space-y-3 text-sm">
                <div>
                  <dt className="text-12 font-medium text-ink-500">
                    Name
                  </dt>
                  <dd className="mt-1 font-medium text-ink">{user.institution.name}</dd>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <dt className="text-12 font-medium text-ink-500">
                      State
                    </dt>
                    <dd className="mt-1 text-ink-700">{user.institution.state}</dd>
                  </div>
                  <div>
                    <dt className="text-12 font-medium text-ink-500">
                      Region
                    </dt>
                    <dd className="mt-1 text-ink-700">{user.institution.region}</dd>
                  </div>
                </div>
              </dl>
            ) : (
              <p className="mt-3 text-13 text-ink-500">
                This account is not attached to a single institution.
              </p>
            )}
          </section>

          <section className="rounded-panel border border-watch bg-watch-soft p-6">
            <h2 className="font-serif text-20 font-semibold text-watch-strong">Session</h2>
            <p className="mt-2 text-13 leading-5 text-watch-strong">
              Access tokens expire eight hours after sign-in. Signing out clears the token from this
              browser and the cached application data.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
