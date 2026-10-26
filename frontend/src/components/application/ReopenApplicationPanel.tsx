import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Lock, RotateCcw } from "lucide-react";

import { Button, Input, Textarea, useToast } from "@/components/ui";
import {
  ApiError,
  reopenApplication,
  type ApplicationDetail,
  type ReopenResult,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { isReopenableStatus } from "@/lib/status";

/**
 * Regulation Bureau control to reopen a wrongly submitted application once.
 *
 * APH 2.3.3d-e requires a fresh TER and the late penalty before the data is
 * unlocked, so this panel calls the fee-aware reopen endpoint instead of the
 * generic workflow action.
 */
export default function ReopenApplicationPanel({
  application,
  token,
}: {
  application: ApplicationDetail;
  token: string;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [resolution, setResolution] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReopenResult | null>(null);

  const alreadyReopened = application.reopen_count >= 1;
  const statusEligible = isReopenableStatus(application.status);
  const canReopen = statusEligible && !alreadyReopened;

  if (!canReopen && !result) {
    return (
      <section className="rounded-panel border border-line bg-surface p-5">
        <div className="flex items-start gap-2.5">
          <Lock aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-500" />
          <div>
            <h2 className="text-14 font-semibold text-ink">Submission locked</h2>
            <p className="mt-1 text-12 leading-5 text-ink-500">
              {application.locked_at
                ? `Locked on ${formatDateTime(application.locked_at)}. `
                : "The application is locked. "}
              {alreadyReopened
                ? "This application has already used its one permitted reopening (APH 2.3.3d-e)."
                : "Data cannot be edited after final submission."}
            </p>
          </div>
        </div>
      </section>
    );
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (reason.trim().length < 10) {
      setError("Give a reason of at least 10 characters for reopening.");
      return;
    }
    if (!acknowledged) {
      setError("Acknowledge that a fresh TER and the late penalty are payable.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const reopened = await reopenApplication(token, application.id, {
        reason: reason.trim(),
        trust_resolution_reference: resolution.trim() || undefined,
        late_penalty_acknowledged: true,
      });
      setResult(reopened);
      setReason("");
      setResolution("");
      setAcknowledged(false);
      toast({
        title: "Application reopened",
        description: reopened.message,
        variant: "success",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["application", application.id] }),
        queryClient.invalidateQueries({ queryKey: ["applications"] }),
        queryClient.invalidateQueries({ queryKey: ["allowed-actions", application.id] }),
        queryClient.invalidateQueries({ queryKey: ["workflow-timeline", application.id] }),
      ]);
    } catch (reopenError) {
      const message =
        reopenError instanceof ApiError
          ? reopenError.message
          : "The application could not be reopened.";
      setError(message);
      toast({
        title: "Reopen failed",
        description: message,
        variant: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    return (
      <section className="rounded-panel border border-ok bg-ok-soft p-5">
        <h2 className="text-14 font-semibold text-ok-strong">
          Application reopened once
        </h2>
        <p className="mt-1 text-13 leading-5 text-ok-strong">{result.message}</p>
        <dl className="mt-3 grid grid-cols-1 gap-2 text-12 text-ok-strong sm:grid-cols-2">
          <div>
            <dt className="font-medium">New TER</dt>
            <dd>
              {(result.quote.total_paise / 100).toLocaleString("en-IN", {
                style: "currency",
                currency: "INR",
                maximumFractionDigits: 0,
              })}
            </dd>
          </div>
          <div>
            <dt className="font-medium">Transactions recorded</dt>
            <dd>{result.transactions.length}</dd>
          </div>
        </dl>
      </section>
    );
  }

  return (
    <section className="rounded-panel border border-line bg-surface p-5">
      <div className="flex items-start gap-2.5">
        <RotateCcw aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-breach-strong" />
        <div>
          <h2 className="text-14 font-semibold text-ink">
            Reopen this application (Regulation Bureau)
          </h2>
          <p className="mt-1 text-12 leading-5 text-ink-500">
            APH 2.3.3d-e allows one reopening of a wrongly submitted application. A fresh TER and
            the late penalty are recorded before the data is unlocked; the Trust resolution
            (Format 3) reference is recorded with the audit entry.
          </p>
        </div>
      </div>

      <form className="mt-4 space-y-3" onSubmit={(event) => void handleSubmit(event)}>
        <Textarea
          label="Reason for reopening"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Explain what was filed incorrectly."
          required
        />
        <Input
          label="Trust resolution reference (Format 3)"
          value={resolution}
          onChange={(event) => setResolution(event.target.value)}
          placeholder="Resolution number and date"
        />
        <label className="flex items-start gap-2 text-12 text-ink-700">
          <input
            type="checkbox"
            className="mt-0.5 size-4 rounded border-line"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          <span>
            I acknowledge that a new TER receipt and the late-submission penalty will be recorded
            and are not adjustable against earlier payments.
          </span>
        </label>

        {error ? (
          <p
            role="alert"
            className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong"
          >
            {error}
          </p>
        ) : null}

        <Button type="submit" variant="destructive" size="sm" disabled={submitting}>
          <RotateCcw aria-hidden="true" className="size-4" />
          {submitting ? "Reopening…" : "Reopen application"}
        </Button>
      </form>
    </section>
  );
}
