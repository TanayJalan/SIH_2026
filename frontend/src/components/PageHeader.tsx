import type { ReactNode } from "react";

export default function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-col gap-5 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <p className="text-12 font-semibold uppercase tracking-[0.16em] text-ink-500">
          {eyebrow}
        </p>
        <h1 className="mt-2 font-serif text-28 font-semibold tracking-tight text-ink sm:text-40">
          {title}
        </h1>
        <p className="mt-2 max-w-3xl text-14 leading-5 text-ink-700">{description}</p>
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </header>
  );
}
