import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye } from "lucide-react";

import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Skeleton,
  StatusPill,
  type StatusPillTone,
  useToast,
} from "@/components/ui";
import { useWorkflowActions } from "@/components/workflow/WorkflowDialogHost";
import {
  ApiError,
  acknowledgeLetter,
  downloadLetterPdf,
  listApplicationAppeals,
  listApplicationDecisions,
  listApplicationLetters,
  type ApplicationDetail,
  type DecisionLetterRecord,
  type DecisionRecord,
} from "@/lib/api";
import { formatDate, formatDateTime, humanizeEnum } from "@/lib/format";
import { useSimulatedNow } from "@/lib/useSimulatedNow";

const OUTCOME_TONES: Record<string, StatusPillTone> = {
  LOA: "compliant",
  EOA: "compliant",
  LOD: "breach",
  LOR: "breach",
  RECOMMEND: "info",
  NOT_RECOMMEND: "watch",
  SEND_BACK: "watch",
};

const LETTER_LABELS: Record<string, string> = {
  LOA: "Letter of Approval",
  EOA: "Extension of Approval",
  LOD: "Letter of Deficiency",
  LOR: "Letter of Rejection",
  SPEAKING_ORDER: "Speaking Order",
  DEFICIENCY_REPORT: "Deficiency Report",
  SHOW_CAUSE: "Show-cause notice",
};

const BODY_LABELS: Record<string, string> = {
  EC: "Executive Committee",
  COUNCIL: "Council",
  SAC: "Standing Appellate Committee",
  SHC: "Standing Hearing Committee",
};

function daysLeftLabel(
  now: Date,
  deadline: string | null | undefined,
): string | null {
  if (!deadline) {
    return null;
  }
  const days = Math.ceil((new Date(deadline).getTime() - now.getTime()) / 86_400_000);
  if (days < 0) {
    return `Closed ${-days} day${days === -1 ? "" : "s"} ago`;
  }
  return `${days} day${days === 1 ? "" : "s"} left to appeal`;
}

function Clause({ text }: { text: string | null }) {
  if (!text) {
    return null;
  }
  return (
    <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 font-medium text-ink-700">
      {text}
    </span>
  );
}

function LetterViewerDialog({ letter }: { letter: DecisionLetterRecord }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="quiet" size="sm">
          <Eye aria-hidden="true" className="size-4" />
          View
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="pr-8">
            {letter.letter_number} · {LETTER_LABELS[letter.letter_type] ?? letter.letter_type}
          </DialogTitle>
          <DialogDescription>
            Issued on {formatDate(letter.issued_on)}. The recorded text is shown here; the PDF
            remains the formal instrument.
          </DialogDescription>
        </DialogHeader>
        <pre className="max-h-[55vh] overflow-y-auto whitespace-pre-wrap rounded-input border border-line bg-paper p-4 font-sans text-13 leading-6 text-ink">
          {letter.body_text || "The letter text is recorded with the PDF instrument."}
        </pre>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="secondary" size="sm">
              Close
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DecisionsTable({ decisions }: { decisions: DecisionRecord[] }) {
  if (decisions.length === 0) {
    return (
      <p className="rounded-input border border-line bg-paper p-4 text-13 leading-5 text-ink-700">
        No committee decision has been recorded on this file yet. Decisions appear here when the
        Executive Committee, SAC or Council records them through the workflow.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-panel border border-line">
      <table className="w-full min-w-[720px] text-left text-13">
        <caption className="sr-only">Recorded committee decisions</caption>
        <thead>
          <tr className="border-b border-line bg-paper">
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Body</th>
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Outcome</th>
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Decided on</th>
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Quorum</th>
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Clause</th>
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Notes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line bg-surface">
          {decisions.map((decision) => (
            <tr key={decision.id}>
              <td className="px-4 py-3 align-top">
                <p className="font-medium text-ink">
                  {BODY_LABELS[decision.body] ?? humanizeEnum(decision.body)}
                </p>
                {decision.committee_name ? (
                  <p className="mt-0.5 text-12 text-ink-500">{decision.committee_name}</p>
                ) : null}
              </td>
              <td className="px-4 py-3 align-top">
                <StatusPill status={OUTCOME_TONES[decision.outcome] ?? "neutral"}>
                  {humanizeEnum(decision.outcome)}
                </StatusPill>
              </td>
              <td className="px-4 py-3 align-top tabular-nums text-ink-700">
                {formatDate(decision.decided_on)}
              </td>
              <td className="px-4 py-3 align-top">
                <StatusPill status={decision.quorum_met ? "compliant" : "breach"}>
                  {decision.quorum_met ? "Met" : "Not met"}
                </StatusPill>
              </td>
              <td className="px-4 py-3 align-top">
                <div className="flex flex-col items-start gap-1">
                  <Clause text={decision.apH_clause} />
                  {decision.ratification ? (
                    <span className="text-12 text-ink-500">
                      Ratified by the Council on {formatDate(decision.ratification.ratified_on)}
                      {decision.ratification.ec_recommendation_ref
                        ? ` · ref ${decision.ratification.ec_recommendation_ref}`
                        : ""}
                      {" "}
                      <Clause text={`(${decision.ratification.apH_clause})`} />
                    </span>
                  ) : null}
                </div>
              </td>
              <td className="max-w-md px-4 py-3 align-top text-12 leading-5 text-ink-700">
                {decision.notes || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AppealPanel({
  application,
  appeals,
  institutionAdmin,
}: {
  application: ApplicationDetail;
  appeals: Awaited<ReturnType<typeof listApplicationAppeals>>;
  institutionAdmin: boolean;
}) {
  const { findAction, openAction } = useWorkflowActions();
  const appealAction = findAction("file_appeal");
  const now = useSimulatedNow();
  const countdown = daysLeftLabel(
    now,
    application.status === "APPEAL_WINDOW" && appeals.length === 0
      ? application.appeal_deadline
      : null,
  );

  if (appeals.length > 0) {
    const appeal = appeals[0];
    return (
      <div className="rounded-input border border-line bg-paper p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-13 font-semibold text-ink">
            Appeal {appeal.loop_no > 1 ? `· loop ${appeal.loop_no}` : ""}
          </h3>
          <StatusPill status={appeal.within_deadline ? "compliant" : "breach"}>
            {appeal.within_deadline ? "Filed within the window" : "Filed late"}
          </StatusPill>
          {appeal.filed_at ? (
            <span className="text-12 text-ink-500">Filed {formatDateTime(appeal.filed_at)}</span>
          ) : null}
        </div>
        <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-12 font-medium text-ink-500">SAC outcome</dt>
            <dd className="mt-0.5 text-13 text-ink">
              {appeal.sac_recommendation
                ? humanizeEnum(appeal.sac_recommendation)
                : "Pending — the Standing Appellate Committee has not recorded its recommendation."}
            </dd>
          </div>
          <div>
            <dt className="text-12 font-medium text-ink-500">Council decision</dt>
            <dd className="mt-0.5 text-13 text-ink">
              {appeal.council_decision ?? "Pending."}
            </dd>
          </div>
        </dl>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Clause text={appeal.apH_clause} />
        </div>
      </div>
    );
  }

  const inWindow = application.status === "APPEAL_WINDOW";
  if (!inWindow) {
    return (
      <p className="rounded-input border border-line bg-paper p-4 text-13 leading-5 text-ink-700">
        No appeal has been filed. The single appeal window opens when a final decision letter is
        issued and closes after seven days (APH 1.11a).
      </p>
    );
  }
  return (
    <div className="rounded-input border border-watch bg-watch-soft p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-13 font-semibold text-watch-strong">
            Appeal window open{countdown ? ` · ${countdown}` : ""}
          </h3>
          <p className="mt-1 text-12 leading-5 text-watch-strong">
            One appeal may be filed against the Letter of Deficiency or Letter of Rejection; a late
            appeal is rejected by the server (APH 1.11a).
          </p>
        </div>
        {institutionAdmin && appealAction ? (
          <Button variant="primary" size="sm" onClick={() => openAction(appealAction)}>
            {appealAction.label}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function LettersTable({
  letters,
  token,
  institutionAdmin,
}: {
  letters: DecisionLetterRecord[];
  token: string;
  institutionAdmin: boolean;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (letters.length === 0) {
    return (
      <p className="rounded-input border border-line bg-paper p-4 text-13 leading-5 text-ink-700">
        No letter has been published on this file yet.
      </p>
    );
  }

  const acknowledge = async (letter: DecisionLetterRecord) => {
    setBusyId(letter.id);
    setError(null);
    try {
      await acknowledgeLetter(token, letter.id);
      await queryClient.invalidateQueries({ queryKey: ["case-letters"] });
      toast({
        title: "Letter acknowledged",
        description: `${letter.letter_number} is now acknowledged by the institution (APH 1.11a).`,
        variant: "success",
      });
    } catch (acknowledgeError) {
      setError(
        acknowledgeError instanceof ApiError
          ? acknowledgeError.message
          : "The acknowledgement could not be recorded.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const now = useSimulatedNow();

  return (
    <div className="overflow-x-auto rounded-panel border border-line">
      <table className="w-full min-w-[760px] text-left text-13">
        <caption className="sr-only">Decision letters published on the portal</caption>
        <thead>
          <tr className="border-b border-line bg-paper">
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Letter</th>
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Issued</th>
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Appeal window</th>
            <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Acknowledgement</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line bg-surface">
          {letters.map((letter) => {
            const countdown = daysLeftLabel(now, letter.appeal_deadline);
            return (
              <tr key={letter.id}>
                <td className="px-4 py-3 align-top">
                  <p className="font-medium text-ink">{letter.letter_number}</p>
                  <p className="mt-0.5 text-12 text-ink-500">
                    {LETTER_LABELS[letter.letter_type] ?? letter.letter_type}
                  </p>
                </td>
                <td className="px-4 py-3 align-top tabular-nums text-ink-700">
                  {formatDate(letter.issued_on)}
                </td>
                <td className="px-4 py-3 align-top">
                  {letter.appeal_deadline ? (
                    <span className="text-12 text-ink-700">{countdown}</span>
                  ) : (
                    <span className="text-12 text-ink-500">—</span>
                  )}
                </td>
                <td className="px-4 py-3 align-top">
                  <StatusPill
                    status={letter.acknowledged_at ? "compliant" : "watch"}
                  >
                    {letter.acknowledged_at ? "Acknowledged" : "Awaiting institution"}
                  </StatusPill>
                  {letter.acknowledged_at ? (
                    <p className="mt-0.5 text-12 text-ink-500">
                      {formatDateTime(letter.acknowledged_at)}
                    </p>
                  ) : null}
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <LetterViewerDialog letter={letter} />
                    <Button
                      variant="quiet"
                      size="sm"
                      onClick={() => void downloadLetterPdf(token, letter)}
                    >
                      <Download aria-hidden="true" className="size-4" />
                      PDF
                    </Button>
                    {institutionAdmin && letter.acknowledged_at === null ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={busyId === letter.id}
                        onClick={() => void acknowledge(letter)}
                      >
                        Acknowledge
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {error ? (
        <p className="border-t border-line bg-breach-soft px-4 py-2 text-12 text-breach-strong">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default function CaseDecisionLetters({
  application,
  token,
  institutionAdmin,
}: {
  application: ApplicationDetail;
  token: string;
  institutionAdmin: boolean;
}) {
  const decisionsQuery = useQuery({
    queryKey: ["case-decisions", application.id],
    queryFn: () => listApplicationDecisions(token, application.id),
    retry: false,
  });
  const appealsQuery = useQuery({
    queryKey: ["case-appeal", application.id],
    queryFn: () => listApplicationAppeals(token, application.id),
    retry: false,
  });
  const lettersQuery = useQuery({
    queryKey: ["case-letters", application.id],
    queryFn: () => listApplicationLetters(token, application.id),
    retry: false,
  });

  return (
    <div className="space-y-5">
      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <h2 className="font-serif text-20 font-semibold text-ink">Decisions</h2>
        <p className="mt-1 text-13 text-ink-500">
          Every decision a committee or Council records, with its clause, quorum and — where it
          exists — the Council ratification (APH 1.10-1.11, 2.25a).
        </p>
        <div className="mt-4">
          {decisionsQuery.isPending ? (
            <div className="space-y-2" role="status">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <span className="sr-only">Loading decisions</span>
            </div>
          ) : decisionsQuery.isError ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {decisionsQuery.error instanceof ApiError
                ? decisionsQuery.error.message
                : "Decisions could not be loaded."}
            </p>
          ) : (
            <DecisionsTable decisions={decisionsQuery.data} />
          )}
        </div>
      </section>

      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <h2 className="font-serif text-20 font-semibold text-ink">Appeal</h2>
        <p className="mt-1 text-13 text-ink-500">
          The single appeal against an LoD or LoR, and where it stands (APH 1.11).
        </p>
        <div className="mt-4">
          {appealsQuery.isPending ? (
            <div className="space-y-2" role="status">
              <Skeleton className="h-10 w-full" />
              <span className="sr-only">Loading appeal</span>
            </div>
          ) : appealsQuery.isError ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {appealsQuery.error instanceof ApiError
                ? appealsQuery.error.message
                : "The appeal record could not be loaded."}
            </p>
          ) : (
            <AppealPanel
              application={application}
              appeals={appealsQuery.data}
              institutionAdmin={institutionAdmin}
            />
          )}
        </div>
      </section>

      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <h2 className="font-serif text-20 font-semibold text-ink">Letters</h2>
        <p className="mt-1 text-13 text-ink-500">
          Letters published on the portal. The institution acknowledges the letter that starts a
          decision; the acknowledgement timestamp can close the appeal window early (APH 1.10,
          1.11a).
        </p>
        <div className="mt-4">
          {lettersQuery.isPending ? (
            <div className="space-y-2" role="status">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <span className="sr-only">Loading letters</span>
            </div>
          ) : lettersQuery.isError ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {lettersQuery.error instanceof ApiError
                ? lettersQuery.error.message
                : "Letters could not be loaded."}
            </p>
          ) : (
            <LettersTable
              letters={lettersQuery.data}
              token={token}
              institutionAdmin={institutionAdmin}
            />
          )}
        </div>
      </section>
    </div>
  );
}
