import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/*
 * The design system uses numeric font-size utilities (text-12, text-13, ...).
 * tailwind-merge treats unknown text-* values as colours, which would drop a
 * real text colour such as `text-surface` when a size utility follows it.
 * Registering the custom sizes keeps colour and size independent.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["12", "13", "14", "16", "20", "28", "40"] }],
    },
  },
});

/** Merge conditional class names while resolving Tailwind conflicts. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
