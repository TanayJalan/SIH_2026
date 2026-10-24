import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  label: string;
  options: SelectOption[];
  id?: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  onBlur?: () => void;
  placeholder?: string;
  hint?: string;
  error?: string;
  disabled?: boolean;
  required?: boolean;
  name?: string;
  containerClassName?: string;
}

export function Select({
  label,
  options,
  id,
  value,
  defaultValue,
  onValueChange,
  onBlur,
  placeholder = "Select an option",
  hint,
  error,
  disabled,
  required,
  name,
  containerClassName,
}: SelectProps) {
  const generatedId = React.useId();
  const selectId = id ?? generatedId;
  const messageId = `${selectId}-message`;
  const message = error ?? hint;

  return (
    <div className={cn("w-full", containerClassName)}>
      <label
        className="mb-1.5 block text-13 font-medium text-ink-700"
        htmlFor={selectId}
      >
        {label}
        {required ? (
          <span className="text-breach-strong" aria-hidden="true">
            {" "}
            *
          </span>
        ) : null}
      </label>
      <SelectPrimitive.Root
        value={value}
        defaultValue={defaultValue}
        onValueChange={onValueChange}
        disabled={disabled}
        required={required}
        name={name}
      >
        <SelectPrimitive.Trigger
          id={selectId}
          onBlur={onBlur}
          aria-invalid={error ? true : undefined}
          aria-describedby={message ? messageId : undefined}
          className={cn(
            "flex h-10 w-full items-center justify-between gap-2 rounded-input border border-line bg-surface px-3 text-left text-14 text-ink transition-colors data-[placeholder]:text-ink-500 focus-visible:border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:border-line disabled:bg-paper disabled:text-ink-300",
            error &&
              "border-breach focus-visible:border-breach focus-visible:ring-breach",
          )}
        >
          <SelectPrimitive.Value placeholder={placeholder} />
          <SelectPrimitive.Icon asChild>
            <ChevronDown
              aria-hidden="true"
              className="size-4 shrink-0 text-ink-500"
            />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            position="popper"
            sideOffset={4}
            className="z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-input border border-line bg-surface text-ink shadow-popover"
          >
            <SelectPrimitive.Viewport className="p-1">
              {options.map((option) => (
                <SelectPrimitive.Item
                  key={option.value}
                  value={option.value}
                  disabled={option.disabled}
                  className="relative flex cursor-default select-none items-center rounded-input py-2 pl-8 pr-2 text-14 text-ink outline-none data-[disabled]:pointer-events-none data-[disabled]:text-ink-300 data-[highlighted]:bg-paper"
                >
                  <span className="absolute left-2 flex size-4 items-center justify-center">
                    <SelectPrimitive.ItemIndicator>
                      <Check aria-hidden="true" className="size-4" />
                    </SelectPrimitive.ItemIndicator>
                  </span>
                  <SelectPrimitive.ItemText>
                    {option.label}
                  </SelectPrimitive.ItemText>
                </SelectPrimitive.Item>
              ))}
            </SelectPrimitive.Viewport>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>
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
}
