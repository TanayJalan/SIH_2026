import * as React from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

export type ToastVariant = "success" | "info" | "error";

export interface ToastInput {
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

interface ToastItem extends ToastInput {
  id: number;
  open: boolean;
}

interface ToastContextValue {
  toast: (input: ToastInput) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

const variantStyles: Record<ToastVariant, string> = {
  success: "border-l-ok",
  info: "border-l-info",
  error: "border-l-breach",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);
  const nextId = React.useRef(0);

  const toast = React.useCallback((input: ToastInput) => {
    nextId.current += 1;
    setToasts((current) => [
      ...current,
      { ...input, id: nextId.current, open: true },
    ]);
  }, []);

  const handleOpenChange = React.useCallback((id: number, open: boolean) => {
    if (!open) {
      setToasts((current) => current.filter((item) => item.id !== id));
    }
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}
        {toasts.map((item) => {
          const variant = item.variant ?? "success";

          return (
            <ToastPrimitive.Root
              key={item.id}
              open={item.open}
              duration={item.duration ?? 5000}
              onOpenChange={(open) => handleOpenChange(item.id, open)}
              className={cn(
                "pointer-events-auto flex w-full items-start gap-3 rounded-panel border border-line border-l-4 bg-surface p-4 text-ink data-[state=closed]:opacity-0",
                variantStyles[variant],
              )}
            >
              <div className="min-w-0 flex-1">
                <ToastPrimitive.Title className="text-14 font-semibold text-ink">
                  {item.title}
                </ToastPrimitive.Title>
                {item.description ? (
                  <ToastPrimitive.Description className="mt-1 text-13 text-ink-700">
                    {item.description}
                  </ToastPrimitive.Description>
                ) : null}
              </div>
              <ToastPrimitive.Close
                type="button"
                aria-label="Dismiss notification"
                className="inline-flex size-7 shrink-0 items-center justify-center rounded-input text-ink-500 transition-colors hover:bg-paper hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                <X aria-hidden="true" className="size-4" />
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          );
        })}
        <ToastPrimitive.Viewport
          aria-label="Notifications"
          className="fixed bottom-0 right-0 z-50 flex w-full max-w-sm flex-col gap-2 p-4 outline-none"
        />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = React.useContext(ToastContext);

  if (!context) {
    throw new Error("useToast must be used inside ToastProvider");
  }

  return context;
}
