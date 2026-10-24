import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-input font-sans text-14 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:pointer-events-none disabled:border-line disabled:bg-paper disabled:text-ink-300",
  {
    variants: {
      variant: {
        primary:
          "bg-saffron text-ink hover:bg-saffron-hover active:bg-saffron",
        secondary: "border border-ink bg-surface text-ink hover:bg-paper",
        quiet: "text-ink-700 hover:bg-paper hover:text-ink",
        destructive: "bg-breach text-surface hover:bg-breach-strong",
      },
      size: {
        sm: "h-8 px-3 text-13",
        md: "h-10 px-4",
        lg: "h-11 px-5 text-16",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";

    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        type={asChild ? undefined : (type ?? "button")}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";
