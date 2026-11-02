import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  Button,
  Input,
  Select,
  Skeleton,
  StatusPill,
  Textarea,
  type StatusPillTone,
  useToast,
} from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";
import {
  ApiError,
  createComplaint,
  getComplaintCatalogue,
  getExcessAdmissionFine,
  getPenalCatalogue,
  issuePenalAction,
  listComplaintPenalActions,
  listComplaints,
  recordEcDecision,
  recordPenalAction,
  recordScscDecision,
  recordShcHearing,
  recordShowCauseReply,
  requestRestoration,
  schedulePenalActionHearing,
  verifyComplaint,
  type ApplicationDetail,
  type ComplaintRecord,
  type PenalActionRecord,
} from "@/lib/api";
import { formatDate, formatInr, humanizeEnum } from "@/lib/format";
import { calendarDaysUntil, useSimulatedNow } from "@/lib/useSimulatedNow";

const STATUS_TONES: Record<string, StatusPillTone> = {
  RECEIVED: "neutral",
  PGRC: "info",
  SCSC: "info",
  SHOW_CAUSE: "watch",
  HEARING: "watch",
  DECIDED: "compliant",
  CLOSED: "neutral",
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

function Section({
  title,
  description,
  children,
  clause,
}: {
  title: string;
  description?: string;
  clause?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-14 font-semibold text-ink">{title}</h2>
        <Clause text={clause} />
      </div>
      {description ? <p className="mt-1 text-13 text-ink-500">{description}</p> : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function CaseComplaints({
  application,
  token,
}: {
  application: ApplicationDetail;
  token: string;
}) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const role = user?.role ?? "";

  const catalogueQuery = useQuery({
    queryKey: ["complaint-catalogue"],
    queryFn: () => getComplaintCatalogue(token),
    retry: false,
  });
  const complaintsQuery = useQuery({
    queryKey: ["complaints", application.institution_id],
    queryFn: () => listComplaints(token, { page: 1, pageSize: 100 }),
    retry: false,
  });
  const penalCatalogueQuery = useQuery({
    queryKey: ["penal-catalogue"],
    queryFn: () => getPenalCatalogue(token),
    retry: false,
  });
  const fineQuery = useQuery({
    queryKey: ["excess-admission-fine", application.id],
    queryFn: () => getExcessAdmissionFine(token, application.id),
    retry: false,
  });

  const complaints = (complaintsQuery.data?.items ?? []).filter(
    (complaint) => complaint.application_id === application.id,
  );

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["complaints"] }),
      queryClient.invalidateQueries({ queryKey: ["complaint-penal-actions"] }),
    ]);
  };

  const canIntake = role === "INSTITUTION_ADMIN";
  const canVerify = ["REGULATION_BUREAU_OFFICER", "COMPLAINT_SCRUTINY_MEMBER", "SUPER_ADMIN"].includes(role);
  const canScsc = ["COMPLAINT_SCRUTINY_MEMBER", "SUPER_ADMIN"].includes(role);
  const canShc = ["SHC_MEMBER", "SUPER_ADMIN"].includes(role);
  const canEc = ["EXECUTIVE_COMMITTEE_MEMBER", "SUPER_ADMIN"].includes(role);
  const canReply = role === "INSTITUTION_ADMIN";

  return (
    <div className="space-y-6">
      <Section
        title="Complaints (Chapter VII)"
        clause="APH 7.10"
        description="PGRC receives and verifies, the SCSC decides, the SHC hears and the EC passes a Speaking Order. Each step cites its clause."
      >
        {catalogueQuery.isError ? (
          <p className="rounded-input border border-line bg-paper p-3 text-13 text-ink-700">
            The complaint lifecycle could not be loaded.
          </p>
        ) : complaintsQuery.isPending || catalogueQuery.isPending ? (
          <div className="space-y-2" role="status">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : (
          <>
            {complaints.length === 0 ? (
              <p className="rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
                No complaint is recorded against this file.
              </p>
            ) : (
              <div className="space-y-4">
                {complaints.map((complaint) => (
                  <ComplaintCard
                    key={complaint.id}
                    complaint={complaint}
                    token={token}
                    catalogue={catalogueQuery.data}
                    canVerify={canVerify}
                    canScsc={canScsc}
                    canShc={canShc}
                    canEc={canEc}
                    canReply={canReply}
                    penalCatalogue={penalCatalogueQuery.data ?? []}
                    onChanged={invalidate}
                  />
                ))}
              </div>
            )}

            {canIntake ? (
              <IntakeForm
                application={application}
                token={token}
                catalogue={catalogueQuery.data}
                onCreated={invalidate}
              />
            ) : null}
          </>
        )}
      </Section>

      {fineQuery.data ? (
        <Section
          title="Excess-admission fine preview"
          clause={fineQuery.data.apH_clause}
          description="Five times the total course fee for every admission above the approved intake (APH 7.3g, 7.4g). Computed from the approved-intake ledger."
        >
          {fineQuery.data.excess_admissions === 0 ? (
            <p className="rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
              No excess admission is recorded for {fineQuery.data.academic_year}.
            </p>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Stat caption="Excess admissions" value={String(fineQuery.data.excess_admissions)} />
                <Stat
                  caption="Total course fee"
                  value={formatInr(fineQuery.data.total_course_fee_paise)}
                />
                <Stat caption="Fine (5×)" value={formatInr(fineQuery.data.fine_paise)} />
              </div>
              <ul className="mt-3 space-y-1 text-12 leading-5 text-ink-500">
                {fineQuery.data.lines.map((line, index) => (
                  <li key={index}>
                    {String(line.course_name)}: approved {String(line.approved_intake)}, admitted{" "}
                    {String(line.admitted_total)} → {String(line.excess_admissions)} excess
                  </li>
                ))}
              </ul>
            </>
          )}
        </Section>
      ) : null}
    </div>
  );
}

function Stat({ caption, value }: { caption: string; value: string }) {
  return (
    <div className="rounded-input border border-line bg-paper p-3">
      <p className="text-12 text-ink-500">{caption}</p>
      <p className="mt-1 text-16 font-semibold tabular-nums text-ink">{value}</p>
    </div>
  );
}

function IntakeForm({
  application,
  token,
  catalogue,
  onCreated,
}: {
  application: ApplicationDetail;
  token: string;
  catalogue: Awaited<ReturnType<typeof getComplaintCatalogue>> | undefined;
  onCreated: () => Promise<void>;
}) {
  const { toast } = useToast();
  const [category, setCategory] = useState("EXCESS_ADMISSION");
  const [description, setDescription] = useState("");
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createComplaint(token, {
        institution_id: application.institution_id,
        application_id: application.id,
        source: "PORTAL",
        category,
        description,
        complainant_name: name || null,
        complainant_contact: contact || null,
        is_anonymous: isAnonymous,
      }),
    onSuccess: async (complaint) => {
      await onCreated();
      setDescription("");
      setName("");
      setContact("");
      setIsAnonymous(false);
      toast({
        title:
          complaint.status === "RECEIVED"
            ? "Complaint rejected at intake"
            : "Complaint recorded",
        description:
          complaint.status === "RECEIVED"
            ? complaint.rejection_reason ?? "Anonymous complaints are not processed (APH 7.10h)."
            : "PGRC will verify the complaint before it goes to the SCSC (APH 7.10b-c).",
        variant: complaint.status === "RECEIVED" ? "error" : "success",
      });
    },
    onError: (mutationError) => {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "The complaint could not be recorded.",
      );
    },
  });

  const submit = () => {
    setError(null);
    if (!description.trim()) {
      setError("Describe the complaint before submitting.");
      return;
    }
    mutation.mutate();
  };

  return (
    <div className="mt-5 rounded-input border border-line bg-paper p-4">
      <h3 className="text-13 font-semibold text-ink">Record a complaint</h3>
      <p className="mt-1 text-12 leading-5 text-ink-500">
        {catalogue?.anonymity_reason ??
          "Anonymous and pseudonymous complaints are not processed (APH 7.10h)."}
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select
          label="Category"
          value={category}
          onValueChange={setCategory}
          options={[
            { value: "EXCESS_ADMISSION", label: "Excess admission" },
            { value: "FACULTY_SHORTAGE", label: "Faculty shortage" },
            { value: "INFRASTRUCTURE", label: "Infrastructure" },
            { value: "FEE_REFUND", label: "Fee refund" },
            { value: "OTHER", label: "Other" },
          ]}
        />
        <Input
          label="Complainant name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Required unless anonymous"
        />
        <Input
          label="Complainant contact"
          value={contact}
          onChange={(event) => setContact(event.target.value)}
          placeholder="Email or phone"
        />
        <label className="mt-6 flex items-center gap-2 text-13 text-ink-700">
          <input
            type="checkbox"
            checked={isAnonymous}
            onChange={(event) => setIsAnonymous(event.target.checked)}
            className="size-4 rounded border-line"
          />
          Anonymous or pseudonymous
        </label>
      </div>
      <div className="mt-3">
        <Textarea
          label="Complaint description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Fictional details of the complaint"
        />
      </div>
      {error ? <p className="mt-2 text-13 text-breach-strong">{error}</p> : null}
      <div className="mt-3 flex items-center justify-between gap-3">
        <Clause text={catalogue?.anonymity_clause ?? "APH 7.10h"} />
        <Button onClick={submit} disabled={mutation.isPending}>
          {mutation.isPending ? "Recording…" : "Record complaint"}
        </Button>
      </div>
    </div>
  );
}

function ComplaintCard({
  complaint,
  token,
  catalogue,
  canVerify,
  canScsc,
  canShc,
  canEc,
  canReply,
  penalCatalogue,
  onChanged,
}: {
  complaint: ComplaintRecord;
  token: string;
  catalogue: Awaited<ReturnType<typeof getComplaintCatalogue>> | undefined;
  canVerify: boolean;
  canScsc: boolean;
  canShc: boolean;
  canEc: boolean;
  canReply: boolean;
  penalCatalogue: Awaited<ReturnType<typeof getPenalCatalogue>>;
  onChanged: () => Promise<void>;
}) {
  const { toast } = useToast();
  const [error, setError] = useState<string | null>(null);
  const now = useSimulatedNow();
  const dueIn = calendarDaysUntil(now, complaint.show_cause_due_on);

  const run = async (action: () => Promise<unknown>, success: string) => {
    setError(null);
    try {
      await action();
      await onChanged();
      toast({ title: success, variant: "success" });
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "The complaint step could not be recorded.",
      );
    }
  };

  return (
    <div className="rounded-input border border-line bg-paper p-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={STATUS_TONES[complaint.status] ?? "neutral"}>
          {humanizeEnum(complaint.status)}
        </StatusPill>
        <span className="text-13 font-medium text-ink">{humanizeEnum(complaint.category)}</span>
        <Clause text={complaint.apH_clause} />
        {complaint.received_on ? (
          <span className="text-12 text-ink-500">Received {formatDate(complaint.received_on)}</span>
        ) : null}
      </div>

      {complaint.rejection_reason ? (
        <div className="mt-3 rounded-input border border-breach bg-breach-soft p-3 text-13 leading-5 text-breach-strong">
          {complaint.rejection_reason}
          <span className="ml-2">
            <Clause text={complaint.rejection_clause} />
          </span>
        </div>
      ) : (
        <>
          <p className="mt-2 text-13 leading-5 text-ink-700">{complaint.description}</p>
          <Lifecycle complaint={complaint} catalogue={catalogue} />

          {complaint.status === "PGRC" && canVerify ? (
            <div className="mt-3 flex justify-end">
              <Button
                size="sm"
                onClick={() =>
                  run(() => verifyComplaint(token, complaint.id), "Complaint verified for the SCSC")
                }
              >
                Verify and send to SCSC
              </Button>
            </div>
          ) : null}

          {complaint.status === "SCSC" && canScsc ? (
            <ScscForm
              token={token}
              complaintId={complaint.id}
              catalogue={catalogue}
              onDone={onChanged}
            />
          ) : null}

          {complaint.status === "SHOW_CAUSE" && canReply ? (
            <ShowCauseForm
              token={token}
              complaintId={complaint.id}
              dueIn={dueIn}
              dueOn={complaint.show_cause_due_on}
              onDone={onChanged}
            />
          ) : null}

          {complaint.status === "HEARING" && canShc ? (
            <ShcForm token={token} complaintId={complaint.id} onDone={onChanged} />
          ) : null}

          {complaint.status === "HEARING" && canEc ? (
            <EcForm token={token} complaintId={complaint.id} onDone={onChanged} />
          ) : null}

          {complaint.ec_decision ? (
            <div className="mt-3 rounded-input border border-line bg-surface p-3">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status="compliant">{humanizeEnum(complaint.ec_decision)}</StatusPill>
                <Clause text="APH 7.10g" />
                {complaint.decided_on ? (
                  <span className="text-12 text-ink-500">Decided {formatDate(complaint.decided_on)}</span>
                ) : null}
              </div>
              <p className="mt-2 whitespace-pre-line text-13 leading-5 text-ink-700">
                {complaint.speaking_order}
              </p>
            </div>
          ) : null}

          <PenalActions
            complaint={complaint}
            token={token}
            catalogue={penalCatalogue}
            canEc={canEc}
            canShc={canShc}
            canRestore={canReply}
            onChanged={onChanged}
          />
        </>
      )}

      {error ? <p className="mt-2 text-13 text-breach-strong">{error}</p> : null}
    </div>
  );
}

function Lifecycle({
  complaint,
  catalogue,
}: {
  complaint: ComplaintRecord;
  catalogue: Awaited<ReturnType<typeof getComplaintCatalogue>> | undefined;
}) {
  const steps = catalogue?.steps ?? [];
  const done: Record<string, boolean> = {
    receive: true,
    verify: complaint.complainant_verified,
    scsc: Boolean(complaint.scsc_decision),
    show_cause: Boolean(complaint.show_cause_replied_on),
    hearing: Boolean(complaint.shc_hearing_on),
    ec: Boolean(complaint.ec_decision),
    speaking_order: Boolean(complaint.speaking_order),
  };
  return (
    <ol className="mt-3 flex flex-wrap gap-2">
      {steps.map((step, index) => (
        <li
          key={step.key}
          className={`rounded-pill px-2.5 py-1 text-11 font-medium ${
            done[step.key] ? "bg-ok-soft text-ok-strong" : "bg-neutral-soft text-ink-500"
          }`}
          title={step.apH_clause}
        >
          {index + 1}. {step.label} · {step.apH_clause}
        </li>
      ))}
    </ol>
  );
}

function ScscForm({
  token,
  complaintId,
  catalogue,
  onDone,
}: {
  token: string;
  complaintId: string;
  catalogue: Awaited<ReturnType<typeof getComplaintCatalogue>> | undefined;
  onDone: () => Promise<void>;
}) {
  const [decision, setDecision] = useState("SHOW_CAUSE");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();
  return (
    <div className="mt-3 rounded-input border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-13 font-semibold text-ink">SCSC decision</h4>
        <Clause text="APH 7.10c" />
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[200px_1fr]">
        <Select
          label="Decision"
          value={decision}
          onValueChange={setDecision}
          options={Object.entries(catalogue?.scsc_decisions ?? {
            WARNING: "Warning",
            SHOW_CAUSE: "Show-cause notice",
            EVC: "Expert Visit Committee",
          }).map(([value, label]) => ({ value, label }))}
        />
        <Input label="Notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
      </div>
      <div className="mt-2 flex justify-end">
        <Button
          size="sm"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await recordScscDecision(token, complaintId, { decision, notes: notes || undefined });
              await onDone();
              toast({ title: "SCSC decision recorded", variant: "success" });
            } finally {
              setBusy(false);
            }
          }}
        >
          Record SCSC decision
        </Button>
      </div>
    </div>
  );
}

function ShowCauseForm({
  token,
  complaintId,
  dueIn,
  dueOn,
  onDone,
}: {
  token: string;
  complaintId: string;
  dueIn: number | null;
  dueOn: string | null;
  onDone: () => Promise<void>;
}) {
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();
  return (
    <div className="mt-3 rounded-input border border-watch bg-watch-soft p-3">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-13 font-semibold text-ink">Show-cause reply</h4>
        <Clause text="APH 7.10d" />
        {dueOn ? (
          <StatusPill status={dueIn !== null && dueIn < 0 ? "breach" : "watch"}>
            {dueIn === null
              ? "No due date"
              : dueIn < 0
                ? `${-dueIn} days overdue`
                : `Due in ${dueIn} day${dueIn === 1 ? "" : "s"}`}
          </StatusPill>
        ) : null}
      </div>
      <div className="mt-2">
        <Textarea
          label="Reply with compliance documents"
          value={reply}
          onChange={(event) => setReply(event.target.value)}
        />
      </div>
      <div className="mt-2 flex justify-end">
        <Button
          size="sm"
          disabled={busy || !reply.trim()}
          onClick={async () => {
            setBusy(true);
            try {
              await recordShowCauseReply(token, complaintId, { reply });
              await onDone();
              toast({ title: "Show-cause reply recorded", variant: "success" });
            } finally {
              setBusy(false);
            }
          }}
        >
          Submit reply
        </Button>
      </div>
    </div>
  );
}

function ShcForm({
  token,
  complaintId,
  onDone,
}: {
  token: string;
  complaintId: string;
  onDone: () => Promise<void>;
}) {
  const [hearingOn, setHearingOn] = useState(new Date().toISOString().slice(0, 10));
  const [findings, setFindings] = useState("");
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();
  return (
    <div className="mt-3 rounded-input border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-13 font-semibold text-ink">SHC hearing record</h4>
        <Clause text="APH 7.10d-e" />
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[180px_1fr]">
        <Input
          label="Hearing date"
          type="date"
          value={hearingOn}
          onChange={(event) => setHearingOn(event.target.value)}
        />
        <Input label="Findings" value={findings} onChange={(event) => setFindings(event.target.value)} />
      </div>
      <div className="mt-2 flex justify-end">
        <Button
          size="sm"
          disabled={busy || !findings.trim()}
          onClick={async () => {
            setBusy(true);
            try {
              await recordShcHearing(token, complaintId, { hearing_on: hearingOn, findings });
              await onDone();
              toast({ title: "SHC hearing recorded", variant: "success" });
            } finally {
              setBusy(false);
            }
          }}
        >
          Record hearing
        </Button>
      </div>
    </div>
  );
}

function EcForm({
  token,
  complaintId,
  onDone,
}: {
  token: string;
  complaintId: string;
  onDone: () => Promise<void>;
}) {
  const [decision, setDecision] = useState("PENAL_ACTION");
  const [speakingOrder, setSpeakingOrder] = useState("");
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();
  return (
    <div className="mt-3 rounded-input border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-13 font-semibold text-ink">Executive Committee decision</h4>
        <Clause text="APH 7.10f-g" />
      </div>
      <div className="mt-2">
        <Select
          label="Decision"
          value={decision}
          onValueChange={setDecision}
          options={[
            { value: "PENAL_ACTION", label: "Penal action with a Speaking Order" },
            { value: "WARNING", label: "Warning" },
            { value: "CLOSE", label: "Close with no further action" },
          ]}
        />
      </div>
      <div className="mt-2">
        <Textarea
          label="Speaking Order"
          value={speakingOrder}
          onChange={(event) => setSpeakingOrder(event.target.value)}
        />
      </div>
      <div className="mt-2 flex justify-end">
        <Button
          size="sm"
          disabled={busy || !speakingOrder.trim()}
          onClick={async () => {
            setBusy(true);
            try {
              await recordEcDecision(token, complaintId, {
                decision,
                speaking_order: speakingOrder,
              });
              await onDone();
              toast({ title: "EC decision published", variant: "success" });
            } finally {
              setBusy(false);
            }
          }}
        >
          Publish Speaking Order
        </Button>
      </div>
    </div>
  );
}

function PenalActions({
  complaint,
  token,
  catalogue,
  canEc,
  canShc,
  canRestore,
  onChanged,
}: {
  complaint: ComplaintRecord;
  token: string;
  catalogue: Awaited<ReturnType<typeof getPenalCatalogue>>;
  canEc: boolean;
  canShc: boolean;
  canRestore: boolean;
  onChanged: () => Promise<void>;
}) {
  const query = useQuery({
    queryKey: ["complaint-penal-actions", complaint.id],
    queryFn: () => listComplaintPenalActions(token, complaint.id),
    retry: false,
  });
  const [violationCode, setViolationCode] = useState("g");
  const [actionType, setActionType] = useState("NO_ADMISSION");
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const entry = catalogue.find((item) => item.code === `APH 7.4${violationCode}`);
  const options = entry?.actions ?? [];

  return (
    <div className="mt-4 border-t border-line pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-13 font-semibold text-ink">Penal actions</h4>
        <Clause text="APH 7.3 / 7.4" />
      </div>

      {query.isPending ? (
        <Skeleton className="mt-2 h-10 w-full" />
      ) : (query.data ?? []).length === 0 ? (
        <p className="mt-2 text-12 text-ink-500">No penal action has been recorded.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {(query.data ?? []).map((action) => (
            <PenalActionRow
              key={action.id}
              action={action}
              token={token}
              canEc={canEc}
              canShc={canShc}
              canRestore={canRestore}
              onChanged={onChanged}
            />
          ))}
        </ul>
      )}

      {canEc ? (
        <div className="mt-3 rounded-input border border-line bg-surface p-3">
          <p className="text-12 leading-5 text-ink-500">
            The action stays a draft until the SHC records a hearing (APH 6.50h proviso).
          </p>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Select
              label="Violation (APH 7.4)"
              value={violationCode}
              onValueChange={(value) => {
                setViolationCode(value);
                const next = catalogue.find((item) => item.code === `APH 7.4${value}`);
                if (next && next.actions.length > 0) {
                  setActionType(next.actions[0].action);
                }
              }}
              options={catalogue.map((item) => ({
                value: item.code.replace("APH 7.4", ""),
                label: `${item.code} · ${item.violation}`,
              }))}
            />
            <Select
              label="Action (APH 7.3)"
              value={actionType}
              onValueChange={setActionType}
              options={options.map((option) => ({ value: option.action, label: option.label }))}
            />
          </div>
          <div className="mt-2 flex items-center justify-between gap-3">
            <Clause text={entry?.code ?? "APH 7.3"} />
            <Button
              size="sm"
              onClick={async () => {
                setError(null);
                try {
                  await recordPenalAction(token, complaint.id, {
                    action_type: actionType,
                    violation_code: violationCode,
                  });
                  await onChanged();
                  toast({ title: "Penal action recorded", variant: "success" });
                } catch (mutationError) {
                  setError(
                    mutationError instanceof ApiError
                      ? mutationError.message
                      : "The penal action could not be recorded.",
                  );
                }
              }}
            >
              Record action
            </Button>
          </div>
          {error ? <p className="mt-2 text-13 text-breach-strong">{error}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

function PenalActionRow({
  action,
  token,
  canEc,
  canShc,
  canRestore,
  onChanged,
}: {
  action: PenalActionRecord;
  token: string;
  canEc: boolean;
  canShc: boolean;
  canRestore: boolean;
  onChanged: () => Promise<void>;
}) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const [orderNumber, setOrderNumber] = useState(`AICTE/PENAL/${new Date().getFullYear()}/0001`);
  const [speakingOrder, setSpeakingOrder] = useState("");
  const [hearingOn, setHearingOn] = useState(new Date().toISOString().slice(0, 10));

  const run = async (fn: () => Promise<unknown>, title: string) => {
    setBusy(true);
    try {
      await fn();
      await onChanged();
      toast({ title, variant: "success" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="rounded-input border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-13 font-medium text-ink">{humanizeEnum(action.action_type)}</span>
        <Clause text={action.apH_clause} />
        <StatusPill status={action.issued_on ? "breach" : action.hearing_on ? "watch" : "neutral"}>
          {action.issued_on ? `Issued ${formatDate(action.issued_on)}` : action.hearing_on ? "Hearing set" : "Draft"}
        </StatusPill>
        {action.fine_paise ? (
          <span className="text-12 tabular-nums text-ink-700">
            Fine {formatInr(action.fine_paise)}
          </span>
        ) : null}
      </div>

      {action.consequences ? (
        <ul className="mt-2 space-y-1 text-12 leading-5 text-ink-500">
          {Object.entries(action.consequences)
            .filter(([key]) => !["apH_clause", "fine_lines"].includes(key))
            .map(([key, value]) => (
              <li key={key}>
                <span className="font-medium text-ink-700">{humanizeEnum(key)}</span>:{" "}
                {Array.isArray(value) ? value.join(", ") : String(value)}
              </li>
            ))}
        </ul>
      ) : null}

      {action.restoration_status ? (
        <p className="mt-2 text-12 text-ink-700">
          Restoration: {humanizeEnum(action.restoration_status)}
          {action.restoration_eligible_from
            ? ` · eligible from ${formatDate(action.restoration_eligible_from)}`
            : ""}{" "}
          <Clause text="APH 7.11a" />
        </p>
      ) : null}

      {!action.issued_on && canShc ? (
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[180px_1fr]">
          <Input
            label="Hearing date"
            type="date"
            value={hearingOn}
            onChange={(event) => setHearingOn(event.target.value)}
          />
          <div className="flex items-end">
            <Button
              size="sm"
              disabled={busy}
              onClick={() =>
                run(
                  () => schedulePenalActionHearing(token, action.id, { hearing_on: hearingOn }),
                  "Hearing scheduled",
                )
              }
            >
              Schedule hearing
            </Button>
          </div>
        </div>
      ) : null}

      {!action.issued_on && canEc && action.hearing_on ? (
        <div className="mt-2 space-y-2">
          <Input
            label="Order number"
            value={orderNumber}
            onChange={(event) => setOrderNumber(event.target.value)}
          />
          <Textarea
            label="Speaking Order"
            value={speakingOrder}
            onChange={(event) => setSpeakingOrder(event.target.value)}
          />
          <div className="flex justify-end">
            <Button
              size="sm"
              disabled={busy || !speakingOrder.trim()}
              onClick={() =>
                run(
                  () =>
                    issuePenalAction(token, action.id, {
                      order_number: orderNumber,
                      speaking_order: speakingOrder,
                    }),
                  "Penal action issued",
                )
              }
            >
              Issue action
            </Button>
          </div>
        </div>
      ) : null}

      {action.issued_on && canRestore && !action.restoration_requested_on ? (
        <div className="mt-2 flex justify-end">
          <Button
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() =>
              run(
                () => requestRestoration(token, action.id),
                "Restoration requested",
              )
            }
          >
            Request restoration (APH 7.11a)
          </Button>
        </div>
      ) : null}
    </li>
  );
}
