import * as React from "react";

import { cn } from "@/lib/utils";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
  error?: string;
  containerClassName?: string;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      hint,
      error,
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
        <textarea
          ref={ref}
          id={id}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            "min-h-24 w-full resize-y rounded-input border border-line bg-surface px-3 py-2.5 text-14 text-ink transition-colors placeholder:text-ink-500 focus-visible:border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:border-line disabled:bg-paper disabled:text-ink-300",
            error &&
              "border-breach focus-visible:border-breach focus-visible:ring-breach",
            className,
          )}
          {...props}
        />
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

Textarea.displayName = "Textarea";
