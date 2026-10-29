import { useQuery } from "@tanstack/react-query";

import {
  Button,
  Skeleton,
  StatusPill,
  type StatusPillTone,
} from "@/components/ui";
import { useWorkflowActions } from "@/components/workflow/WorkflowDialogHost";
import { ApiError, type FeeKind } from "@/lib/api";
import {
  getApplicationFee,
  getSecurityDepositQuote,
  listApplicationFeeTransactions,
  type ApplicationDetail,
} from "@/lib/api";
import { formatDateTime, formatInr, humanizeEnum } from "@/lib/format";

const KIND_TONES: Record<FeeKind, StatusPillTone> = {
  TER: "info",
  PENALTY: "breach",
  REFUND: "compliant",
  DEDUCTION: "watch",
};

function Clause({ text }: { text: string | null | undefined }) {
  if (!text) {
    return null;
  }
  return (
    <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 font-medium text-ink-700">
      {text}
    </span>
  );
}

function FeeStat({
  caption,
  value,
}: {
  caption: string;
  value: number;
}) {
  return (
    <div className="flex-1 rounded-input border border-line bg-paper px-4 py-3">
      <p className="text-12 font-medium text-ink-500">{caption}</p>
      <p className="mt-1 tabular-nums text-18 font-semibold text-ink">{formatInr(value)}</p>
    </div>
  );
}

export default function CaseFees({
  application,
  token,
  institutionAdmin,
}: {
  application: ApplicationDetail;
  token: string;
  institutionAdmin: boolean;
}) {
  const { findAction, openAction } = useWorkflowActions();
  const payAction = findAction("pay_ter");
  const depositAction = findAction("pay_security_deposit");

  const feeQuery = useQuery({
    queryKey: ["fee", application.id],
    queryFn: () => getApplicationFee(token, application.id),
    enabled: Boolean(token && application.id),
    retry: false,
  });
  const transactionsQuery = useQuery({
    queryKey: ["fee-transactions", application.id],
    queryFn: () => listApplicationFeeTransactions(token, application.id),
    enabled: Boolean(token && application.id),
    retry: false,
  });
  const depositQuery = useQuery({
    queryKey: ["security-deposit-quote", application.id],
    queryFn: () => getSecurityDepositQuote(token, application.id),
    enabled: Boolean(token && application.id),
    retry: false,
  });

  const quote = feeQuery.data;

  return (
    <div className="space-y-5">
      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="font-serif text-20 font-semibold text-ink">Fees</h2>
            <p className="mt-1 text-13 text-ink-500">
              TER and deposit amounts come from the configured fee schedules; every line cites its
              APH clause. Amounts are illustrative demo values — verify against the current AICTE
              Approval Process Handbook.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {institutionAdmin && payAction && quote && quote.due_paise > 0 ? (
              <Button variant="primary" size="sm" onClick={() => openAction(payAction)}>
                {payAction.label}
              </Button>
            ) : null}
            {institutionAdmin && depositAction ? (
              <Button variant="secondary" size="sm" onClick={() => openAction(depositAction)}>
                {depositAction.label}
              </Button>
            ) : null}
          </div>
        </div>

        {feeQuery.isPending ? (
          <div className="mt-4 space-y-2" role="status">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-2/3" />
            <span className="sr-only">Loading fee quote</span>
          </div>
        ) : feeQuery.isError || !quote ? (
          <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
            {feeQuery.error instanceof ApiError
              ? feeQuery.error.message
              : "The fee position could not be loaded."}
          </p>
        ) : (
          <>
            <div className="mt-4 flex flex-wrap gap-3">
              <FeeStat caption="Total TER" value={quote.total_paise} />
              <FeeStat caption="Paid" value={quote.paid_paise} />
              <FeeStat caption="Refunded" value={quote.refunded_paise} />
              <FeeStat caption="Due" value={quote.due_paise} />
            </div>
            <p className="mt-2 flex flex-wrap items-center gap-2 text-12 text-ink-500">
              <StatusPill status={quote.is_paid ? "compliant" : quote.due_paise > 0 ? "watch" : "neutral"}>
                {quote.is_paid ? "Paid in full" : quote.due_paise > 0 ? "Partly paid" : "No amount due"}
              </StatusPill>
              {quote.ter_receipt_no ? (
                <span>
                  Receipt {quote.ter_receipt_no}
                  {quote.ter_paid_at ? ` · paid ${formatDateTime(quote.ter_paid_at)}` : ""}
                </span>
              ) : null}
              {quote.late_submission ? (
                <span className="font-medium text-breach-strong">
                  Late submission penalty applies (APH 2.3.3c)
                </span>
              ) : null}
            </p>

            {quote.lines.length > 0 ? (
              <div className="mt-4 overflow-x-auto rounded-panel border border-line">
                <table className="w-full min-w-[640px] text-left text-13">
                  <caption className="sr-only">Fee quotation lines</caption>
                  <thead>
                    <tr className="border-b border-line bg-paper">
                      <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Item</th>
                      <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Units</th>
                      <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Unit amount</th>
                      <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">Amount</th>
                      <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Clause</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line bg-surface">
                    {quote.lines.map((line) => (
                      <tr key={line.item_code}>
                        <td className="px-4 py-3 align-top font-medium text-ink">{line.label}</td>
                        <td className="px-4 py-3 align-top tabular-nums text-ink-700">
                          {line.units} {line.unit}
                        </td>
                        <td className="px-4 py-3 align-top tabular-nums text-ink-700">
                          {formatInr(line.unit_amount_paise)}
                        </td>
                        <td className="px-4 py-3 text-right align-top tabular-nums font-medium text-ink">
                          {formatInr(line.amount_paise)}
                        </td>
                        <td className="px-4 py-3 align-top">
                          <Clause text={line.apH_clause} />
                          {line.needs_verification ? (
                            <p className="mt-1 text-11 text-watch-strong">
                              Illustrative — needs verification
                            </p>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        )}
      </section>

      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <h2 className="text-14 font-semibold text-ink">Payment and refund history</h2>
        <p className="mt-1 text-13 text-ink-500">
          Immutable money movements recorded on the file; refunds are never netted into a later
          payment.
        </p>
        <div className="mt-4">
          {transactionsQuery.isPending ? (
            <div className="space-y-2" role="status">
              <Skeleton className="h-10 w-full" />
              <span className="sr-only">Loading fee history</span>
            </div>
          ) : transactionsQuery.isError ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {transactionsQuery.error instanceof ApiError
                ? transactionsQuery.error.message
                : "The fee history could not be loaded."}
            </p>
          ) : transactionsQuery.data.length === 0 ? (
            <p className="rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
              No payment or refund has been recorded yet.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-panel border border-line">
              <table className="w-full min-w-[640px] text-left text-13">
                <caption className="sr-only">Fee transactions</caption>
                <thead>
                  <tr className="border-b border-line bg-paper">
                    <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Kind</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Item</th>
                    <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">Amount</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Receipt</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Recorded</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Clause</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line bg-surface">
                  {transactionsQuery.data.map((transaction) => (
                    <tr key={transaction.id}>
                      <td className="px-4 py-3 align-top">
                        <StatusPill status={KIND_TONES[transaction.kind]}>
                          {humanizeEnum(transaction.kind)}
                        </StatusPill>
                      </td>
                      <td className="px-4 py-3 align-top text-ink-700">{transaction.item_code}</td>
                      <td className="px-4 py-3 text-right align-top tabular-nums font-medium text-ink">
                        {formatInr(transaction.amount_paise)}
                      </td>
                      <td className="px-4 py-3 align-top font-mono text-12 text-ink-700">
                        {transaction.receipt_no ?? "—"}
                      </td>
                      <td className="px-4 py-3 align-top tabular-nums text-ink-700">
                        {transaction.paid_at ? formatDateTime(transaction.paid_at) : "—"}
                      </td>
                      <td className="px-4 py-3 align-top">
                        <Clause text={transaction.apH_clause} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {depositQuery.data ? (
        <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
          <h2 className="text-14 font-semibold text-ink">Security Deposit (Table 1.4)</h2>
          <p className="mt-1 text-13 text-ink-500">
            {depositQuery.data.penalty_windows}
          </p>
          <div className="mt-4 overflow-x-auto rounded-panel border border-line">
            <table className="w-full min-w-[640px] text-left text-13">
              <caption className="sr-only">Security Deposit per programme</caption>
              <thead>
                <tr className="border-b border-line bg-paper">
                  <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Programme family</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Level</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Leased</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">Deposit</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Penalty</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">Due</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {depositQuery.data.lines.map((line) => (
                  <tr key={`${line.programme_family}-${line.level}`}>
                    <td className="px-4 py-3 align-top font-medium text-ink">
                      {humanizeEnum(line.programme_family)}
                    </td>
                    <td className="px-4 py-3 align-top text-ink-700">{line.level}</td>
                    <td className="px-4 py-3 align-top">
                      {line.leased ? (
                        <span className="text-12 text-watch-strong">Doubled (leased)</span>
                      ) : (
                        <span className="text-12 text-ink-500">No</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right align-top tabular-nums text-ink-700">
                      {formatInr(line.deposit_paise)}
                    </td>
                    <td className="px-4 py-3 align-top tabular-nums text-ink-700">
                      {line.penalty_percent}%
                    </td>
                    <td className="px-4 py-3 text-right align-top tabular-nums font-medium text-ink">
                      {formatInr(line.total_due_paise)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-3 space-y-1 text-12 leading-5 text-ink-500">
            {depositQuery.data.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
