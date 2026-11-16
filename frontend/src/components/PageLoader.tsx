import { Skeleton } from "./ui/Skeleton";

/**
 * Content-area placeholder shown while a lazy route module is fetched.
 *
 * The placeholder is absolutely positioned so it never contributes height to
 * the document: when the real page mounts there is no element left to move.
 * Main reserves a viewport of height, so the footer also stays put.
 */
export default function PageLoader({ label = "Loading page" }: { label?: string }) {
  return (
    <div
      className="absolute inset-0 space-y-4 px-4 py-6 sm:px-6 lg:px-8 lg:py-10"
      role="status"
      aria-live="polite"
    >
      <Skeleton className="h-5 w-40" />
      <Skeleton className="h-9 w-2/3 max-w-md" />
      <Skeleton className="h-4 w-full max-w-xl" />
      <div className="grid grid-cols-1 gap-4 pt-4 sm:grid-cols-3">
        <Skeleton className="h-24 w-full rounded-panel" />
        <Skeleton className="h-24 w-full rounded-panel" />
        <Skeleton className="h-24 w-full rounded-panel" />
      </div>
      <Skeleton className="h-64 w-full rounded-panel" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
