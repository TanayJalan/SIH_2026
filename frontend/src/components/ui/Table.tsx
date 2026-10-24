import * as React from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";

export type TableDensity = "comfortable" | "dense";
export type TableSortDirection = "asc" | "desc" | "none";

const TableContext = React.createContext<{ density: TableDensity }>({
  density: "comfortable",
});

export interface TableProps
  extends React.TableHTMLAttributes<HTMLTableElement> {
  density?: TableDensity;
  containerClassName?: string;
}

export function Table({
  density = "comfortable",
  containerClassName,
  className,
  children,
  ...props
}: TableProps) {
  return (
    <TableContext.Provider value={{ density }}>
      <div
        className={cn(
          "relative w-full overflow-auto rounded-panel border border-line bg-surface",
          containerClassName,
        )}
      >
        <table
          className={cn(
            "w-full border-collapse text-left text-14 text-ink",
            className,
          )}
          {...props}
        >
          {children}
        </table>
      </div>
    </TableContext.Provider>
  );
}

export function TableHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn(
        "border-b border-line bg-paper [&_tr]:border-b [&_tr]:border-line",
        className,
      )}
      {...props}
    />
  );
}

export function TableBody({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={cn("[&_tr:last-child]:border-0", className)} {...props} />
  );
}

export function TableFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tfoot
      className={cn("border-t border-line bg-paper font-medium", className)}
      {...props}
    />
  );
}

export function TableRow({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        "border-b border-line transition-colors hover:bg-paper data-[state=selected]:bg-paper",
        className,
      )}
      {...props}
    />
  );
}

export interface TableHeadProps
  extends React.ThHTMLAttributes<HTMLTableCellElement> {
  sortDirection?: TableSortDirection;
  onSort?: () => void;
}

function SortIcon({ direction }: { direction: TableSortDirection }) {
  if (direction === "asc") {
    return <ArrowUp aria-hidden="true" className="size-3.5" />;
  }
  if (direction === "desc") {
    return <ArrowDown aria-hidden="true" className="size-3.5" />;
  }
  return <ChevronsUpDown aria-hidden="true" className="size-3.5 text-ink-300" />;
}

export function TableHead({
  className,
  children,
  scope = "col",
  sortDirection = "none",
  onSort,
  ...props
}: TableHeadProps) {
  const { density } = React.useContext(TableContext);
  const ariaSort =
    sortDirection === "asc"
      ? "ascending"
      : sortDirection === "desc"
        ? "descending"
        : "none";

  return (
    <th
      scope={scope}
      aria-sort={onSort ? ariaSort : undefined}
      className={cn(
        "sticky top-0 z-10 bg-paper text-left align-middle text-12 font-semibold text-ink-700",
        density === "dense" ? "px-3 py-2" : "px-4 py-3",
        className,
      )}
      {...props}
    >
      {onSort ? (
        <button
          type="button"
          onClick={onSort}
          className="inline-flex min-h-6 w-full items-center gap-1.5 rounded-input text-left text-12 font-semibold text-ink-700 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {children}
          <SortIcon direction={sortDirection} />
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export function TableCell({
  className,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  const { density } = React.useContext(TableContext);

  return (
    <td
      className={cn(
        "align-middle text-14 tabular-nums text-ink",
        density === "dense" ? "px-3 py-2" : "px-4 py-3",
        className,
      )}
      {...props}
    />
  );
}

export function TableCaption({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableCaptionElement>) {
  return (
    <caption
      className={cn("px-4 py-3 text-left text-12 text-ink-500", className)}
      {...props}
    />
  );
}
