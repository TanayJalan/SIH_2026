import type { ReactNode } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui";
import type { Role } from "../lib/api";
import { navItemsFor } from "../lib/roles";

function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex min-w-6 items-center justify-center rounded-input border border-line bg-paper px-1.5 py-0.5 font-sans text-12 font-medium text-ink-700">
      {children}
    </kbd>
  );
}

function ShortcutRow({
  keys,
  children,
}: {
  keys: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <dt className="text-14 text-ink-700">{children}</dt>
      <dd className="flex shrink-0 items-center gap-1">{keys}</dd>
    </div>
  );
}

export default function KeyboardShortcutsDialog({
  open,
  onOpenChange,
  role,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  role: Role;
}) {
  const navItems = navItemsFor(role).filter((item) => item.shortcut);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>
            Move around the approval workspace without leaving the keyboard.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-5 space-y-6">
          <section>
            <h3 className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-500">
              Go to
            </h3>
            <dl className="mt-1 divide-y divide-line">
              {navItems.map((item) => {
                const [prefix, key] = item.shortcut?.split(" ") ?? [];
                return (
                  <ShortcutRow
                    key={item.to}
                    keys={
                      <>
                        <Kbd>{prefix}</Kbd>
                        <span className="text-12 text-ink-300">then</span>
                        <Kbd>{key}</Kbd>
                      </>
                    }
                  >
                    {item.label}
                  </ShortcutRow>
                );
              })}
            </dl>
          </section>

          <section>
            <h3 className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-500">
              Everywhere
            </h3>
            <dl className="mt-1 divide-y divide-line">
              <ShortcutRow
                keys={
                  <>
                    <Kbd>⌘</Kbd>
                    <span className="text-12 text-ink-300">/</span>
                    <Kbd>Ctrl</Kbd>
                    <Kbd>K</Kbd>
                  </>
                }
              >
                Open global search
              </ShortcutRow>
              <ShortcutRow keys={<Kbd>?</Kbd>}>Show this help</ShortcutRow>
              <ShortcutRow keys={<Kbd>Esc</Kbd>}>Close a dialog or menu</ShortcutRow>
              <ShortcutRow
                keys={
                  <>
                    <Kbd>↑</Kbd>
                    <Kbd>↓</Kbd>
                  </>
                }
              >
                Move between search results
              </ShortcutRow>
              <ShortcutRow keys={<Kbd>↵</Kbd>}>Open the selected result</ShortcutRow>
            </dl>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
