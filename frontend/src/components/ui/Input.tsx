import * as React from "react";

import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
  suffix?: string;
  containerClassName?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      hint,
      error,
      suffix,
      containerClassName,
      className,
      id: idProp,
      required,
      "aria-describedby": describedByProp,
      ...props
    },
    ref,
  ) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;
    const messageId = `${id}-message`;
    const message = error ?? hint;
    const describedBy =
      [describedByProp, message ? messageId : undefined]
        .filter(Boolean)
        .join(" ") || undefined;

    return (
      <div className={cn("w-full", containerClassName)}>
        <label
          className="mb-1.5 block text-13 font-medium text-ink-700"
          htmlFor={id}
        >
          {label}
          {required ? (
            <span className="text-breach-strong" aria-hidden="true">
              {" "}
              *
            </span>
          ) : null}
        </label>
        <div className="relative">
          <input
            ref={ref}
            id={id}
            required={required}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={cn(
              "h-10 w-full rounded-input border border-line bg-surface px-3 text-14 text-ink transition-colors placeholder:text-ink-500 focus-visible:border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:border-line disabled:bg-paper disabled:text-ink-300",
              suffix &&
                "pr-24 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
              error &&
                "border-breach focus-visible:border-breach focus-visible:ring-breach",
              className,
            )}
            {...props}
          />
          {suffix ? (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-12 text-ink-500"
            >
              {suffix}
            </span>
          ) : null}
        </div>
        {message ? (
          <p
            id={messageId}
            className={cn(
              "mt-1.5 text-13",
              error ? "text-breach-strong" : "text-ink-500",
            )}
          >
            {message}
          </p>
        ) : null}
      </div>
    );
  },
);

Input.displayName = "Input";
