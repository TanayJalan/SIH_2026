import { useEffect, useRef, useState } from "react";

interface CountUpNumberProps {
  value: number;
  format: (value: number) => string;
  className?: string;
  durationMs?: number;
}

function readReducedMotionPreference(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(
    readReducedMotionPreference,
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = () => setPrefersReducedMotion(mediaQuery.matches);
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  return prefersReducedMotion;
}

export default function CountUpNumber({
  value,
  format,
  className,
  durationMs = 900,
}: CountUpNumberProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const [displayValue, setDisplayValue] = useState(() =>
    prefersReducedMotion ? value : 0,
  );
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (prefersReducedMotion || hasAnimated.current) {
      setDisplayValue(value);
      return;
    }

    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / durationMs, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(value * eased);
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        hasAnimated.current = true;
        setDisplayValue(value);
      }
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [durationMs, prefersReducedMotion, value]);

  return (
    <>
      <span aria-hidden="true" className={className}>
        {format(displayValue)}
      </span>
      <span className="sr-only">{format(value)}</span>
    </>
  );
}
