export default function FullPageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="grid min-h-screen place-items-center bg-paper" role="status">
      <div className="flex flex-col items-center gap-4 text-center">
        <span className="grid size-11 place-items-center rounded-pill border-2 border-line border-t-ink motion-safe:animate-spin" />
        <span className="text-14 font-medium text-ink-700">{label}</span>
      </div>
    </div>
  );
}
