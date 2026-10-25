import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Hash,
  Scale,
  ShieldCheck,
  UserCheck,
  Users,
} from "lucide-react";

import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Select,
  Skeleton,
  StatusPill,
} from "../ui";
import {
  ApiError,
  checkQuorum,
  getCommitteesForApplication,
  selectCommittee,
  type CommitteeSelectionOut,
} from "@/lib/api";
import { formatDateTime, humanizeEnum } from "@/lib/format";

interface CaseCommitteesProps {
  applicationId: string;
  token: string;
  canSelect: boolean;
}

const COMMITTEE_TYPE_OPTIONS = [
  { value: "SCRUTINY", label: "Scrutiny Committee (APH 16.3/16.4)" },
  { value: "EVC", label: "Expert Visit Committee (APH 16.5)" },
  { value: "SHC", label: "Standing Hearing Committee (APH 16.6)" },
  { value: "SAC", label: "Standing Appellate Committee (APH 16.6)" },
  { value: "SCSC", label: "Standing Complaint Scrutiny (APH 16.7)" },
];

const QUORUM_TYPE_OPTIONS = [
  { value: "SCRUTINY", label: "Scrutiny Committee (APH 16.3/4)" },
  { value: "EVC", label: "Expert Visit Committee (APH 16.5)" },
  { value: "SHC", label: "Standing Hearing Committee (APH 16.6)" },
  { value: "SAC", label: "Standing Appellate Committee (APH 16.6)" },
  { value: "SCSC", label: "Standing Complaint Scrutiny (APH 16.7)" },
  { value: "EC", label: "Executive Committee (APH 16.2)" },
  { value: "COUNCIL", label: "AICTE Council (APH 16.1)" },
];

const MEETING_MODE_OPTIONS = [
  { value: "ONLINE", label: "Online (Virtual)" },
  { value: "HYBRID", label: "Hybrid" },
  { value: "PHYSICAL", label: "Physical (In-Person)" },
];

export default function CaseCommittees({
  applicationId,
  token,
  canSelect,
}: CaseCommitteesProps) {
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<string>("SCRUTINY");
  const [selectedMode, setSelectedMode] = useState<"ONLINE" | "HYBRID" | "PHYSICAL">("ONLINE");
  const [includeCoOpt, setIncludeCoOpt] = useState(false);
  const [customSeed, setCustomSeed] = useState("");
  const [copiedSeed, setCopiedSeed] = useState<string | null>(null);

  // Quorum verification calculator state
  const [quorumType, setQuorumType] = useState<string>("SCSC");
  const [presentCount, setPresentCount] = useState<number>(2);

  const committeesQuery = useQuery({
    queryKey: ["committees", applicationId],
    queryFn: () => getCommitteesForApplication(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const quorumQuery = useQuery({
    queryKey: ["quorum", quorumType, presentCount],
    queryFn: () => checkQuorum(token, quorumType, presentCount),
    enabled: Boolean(token && quorumType),
    retry: false,
  });

  const selectMutation = useMutation({
    mutationFn: () =>
      selectCommittee(token, {
        application_id: applicationId,
        committee_type: selectedType,
        mode: selectedMode,
        include_co_opt: includeCoOpt,
        selection_seed: customSeed.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["committees", applicationId] });
      setIsDialogOpen(false);
      setCustomSeed("");
    },
  });

  const committees = committeesQuery.data ?? [];

  const handleCopySeed = (seed: string) => {
    navigator.clipboard.writeText(seed);
    setCopiedSeed(seed);
    setTimeout(() => setCopiedSeed(null), 2000);
  };

  return (
    <section className="space-y-6">
      <div className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-serif text-20 font-semibold text-ink">
                Committees & Expert Panels
              </h2>
              <span className="rounded bg-sky-100 px-2 py-0.5 text-11 font-medium text-sky-800">
                APH Annexure-16
              </span>
            </div>
            <p className="mt-1 text-13 text-ink-500">
              Automated, deterministic committee member draws from the 30+ expert pool with state-conflict exclusion.
            </p>
          </div>
          {canSelect && (
            <Button variant="primary" size="sm" onClick={() => setIsDialogOpen(true)}>
              <Users className="mr-1.5 h-4 w-4" />
              Constitute Committee
            </Button>
          )}
        </div>

        {committeesQuery.isPending ? (
          <div className="mt-5 space-y-3" role="status">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-32 w-full" />
            ))}
          </div>
        ) : committeesQuery.isError ? (
          <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
            {committeesQuery.error instanceof ApiError
              ? committeesQuery.error.message
              : "Committee selections could not be loaded."}
          </p>
        ) : committees.length === 0 ? (
          <div className="mt-5 rounded-input border border-dashed border-line bg-paper p-8 text-center">
            <Users className="mx-auto h-8 w-8 text-ink-300" />
            <p className="mt-2 text-14 font-medium text-ink">No committee constituted yet</p>
            <p className="mt-1 text-12 text-ink-500">
              Committees are drawn automatically based on the institution's chapter and application stage.
            </p>
            {canSelect && (
              <Button
                variant="secondary"
                size="sm"
                className="mt-4"
                onClick={() => setIsDialogOpen(true)}
              >
                Constitute First Committee
              </Button>
            )}
          </div>
        ) : (
          <div className="mt-5 space-y-5">
            {committees.map((committee) => (
              <CommitteeCard
                key={committee.committee_id}
                committee={committee}
                onCopySeed={handleCopySeed}
                copiedSeed={copiedSeed}
              />
            ))}
          </div>
        )}
      </div>

      {/* Quorum Calculator & Auditor Section */}
      <div className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="flex items-center gap-2 font-serif text-16 font-semibold text-ink">
              <Scale className="h-4 w-4 text-brand" />
              Quorum Verification Calculator
            </h3>
            <p className="mt-0.5 text-12 text-ink-500">
              Verify statutory meeting quorum requirements per APH 16.2 (EC) and APH 16.7 (SCSC).
            </p>
          </div>
          {quorumQuery.data && (
            <StatusPill status={quorumQuery.data.quorum_met ? "compliant" : "breach"}>
              {quorumQuery.data.quorum_met ? "Quorum Satisfied" : "Quorum Not Met"}
            </StatusPill>
          )}
        </div>

        <div className="mt-4 grid grid-cols-1 items-end gap-4 sm:grid-cols-3">
          <Select
            label="Committee Type"
            options={QUORUM_TYPE_OPTIONS}
            value={quorumType}
            onValueChange={setQuorumType}
          />

          <Input
            label="Members Present"
            type="number"
            min={0}
            max={50}
            value={presentCount}
            onChange={(e) => setPresentCount(Math.max(0, parseInt(e.target.value, 10) || 0))}
          />

          <div className="rounded-input border border-line bg-paper p-3 text-12">
            <span className="font-semibold text-ink">Norm Rule ({quorumQuery.data?.apH_clause ?? "APH"}):</span>
            <p className="mt-1 text-ink-500">
              {quorumQuery.data?.quorum_description || "Required seats must be present."}
            </p>
            <p className="mt-1 text-11 font-medium text-ink-400">
              Required: {quorumQuery.data?.quorum_required ?? "--"} | Present: {presentCount}
            </p>
          </div>
        </div>
      </div>

      {/* Constitution Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Constitute Committee</DialogTitle>
            <DialogDescription>
              Draw members automatically from the approved expert pool per APH Annexure-16.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <Select
              label="Committee Type"
              options={COMMITTEE_TYPE_OPTIONS}
              value={selectedType}
              onValueChange={setSelectedType}
            />

            <Select
              label="Meeting Mode"
              options={MEETING_MODE_OPTIONS}
              value={selectedMode}
              onValueChange={(v) => setSelectedMode(v as "ONLINE" | "HYBRID" | "PHYSICAL")}
            />

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="coopt"
                checked={includeCoOpt}
                onChange={(e) => setIncludeCoOpt(e.target.checked)}
                className="h-4 w-4 rounded border-line text-brand focus:ring-brand"
              />
              <label htmlFor="coopt" className="text-12 font-medium text-ink">
                Include Co-opted State/University Representative (APH 16 Note)
              </label>
            </div>

            <Input
              label="Custom Selection Seed (Optional, for replay)"
              placeholder="Leave blank for auto-generated seed"
              value={customSeed}
              onChange={(e) => setCustomSeed(e.target.value)}
              hint="Supplying the same seed produces the identical expert selection for audit verification."
            />

            {selectMutation.isError && (
              <p className="rounded-input border border-breach bg-breach-soft p-2.5 text-12 text-breach-strong">
                {selectMutation.error instanceof ApiError
                  ? selectMutation.error.message
                  : "Selection failed."}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button variant="secondary" onClick={() => setIsDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={selectMutation.isPending}
              onClick={() => selectMutation.mutate()}
            >
              {selectMutation.isPending ? "Selecting Members..." : "Run Automated Draw"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function CommitteeCard({
  committee,
  onCopySeed,
  copiedSeed,
}: {
  committee: CommitteeSelectionOut;
  onCopySeed: (seed: string) => void;
  copiedSeed: string | null;
}) {
  return (
    <div className="rounded-input border border-line p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <StatusPill status="info">{humanizeEnum(committee.committee_type)}</StatusPill>
          <span className="text-12 font-medium text-ink-700">
            Mode: {humanizeEnum(committee.mode)}
          </span>
          <span className="text-12 text-ink-400">·</span>
          <span className="text-12 text-ink-500">
            Selected: {formatDateTime(committee.selected_at ?? "")}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded bg-paper px-2 py-1 text-11 text-ink-600">
            <Hash className="h-3 w-3 text-ink-400" />
            <span className="font-mono">{committee.selection_seed.slice(0, 10)}...</span>
            <button
              onClick={() => onCopySeed(committee.selection_seed)}
              className="ml-1 text-ink-400 hover:text-ink-700"
              title="Copy selection seed"
            >
              {copiedSeed === committee.selection_seed ? (
                <CheckCircle2 className="h-3 w-3 text-green-600" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </button>
          </div>

          <StatusPill status={committee.quorum_met ? "compliant" : "watch"}>
            Quorum: {committee.quorum_required} required
          </StatusPill>
        </div>
      </div>

      {committee.warnings.length > 0 && (
        <div className="mt-3 rounded-input border border-amber-200 bg-amber-50 p-2.5 text-12 text-amber-900">
          <div className="flex items-center gap-1.5 font-medium">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-700" />
            Selection notice:
          </div>
          <ul className="mt-1 list-disc pl-4 space-y-0.5">
            {committee.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Member Seats */}
      <div className="mt-4 space-y-3">
        <h4 className="text-11 font-semibold uppercase tracking-wider text-ink-500">
          Constituted Members ({committee.seats.length})
        </h4>

        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {committee.seats.map((seat, i) => (
            <div key={i} className="rounded border border-line bg-paper p-3 text-12">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-10 font-bold uppercase tracking-wider text-brand">
                    {seat.seat_label}
                  </span>
                  <p className="mt-0.5 font-semibold text-ink">{seat.expert_name}</p>
                </div>
                <span className="rounded bg-gray-100 px-1.5 py-0.5 text-10 font-medium text-gray-600">
                  Fictional
                </span>
              </div>

              {seat.reasons.length > 0 && (
                <div className="mt-2 space-y-1 border-t border-line/60 pt-2 text-11 text-ink-500">
                  {seat.reasons.map((r, rIdx) => (
                    <div key={rIdx} className="flex items-start gap-1">
                      <ShieldCheck className="mt-0.5 h-3 w-3 flex-shrink-0 text-emerald-600" />
                      <span>{r}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {committee.co_opted && (
            <div className="rounded border border-dashed border-line bg-paper p-3 text-12">
              <span className="text-10 font-bold uppercase tracking-wider text-sky-700">
                {committee.co_opted.seat_label} (Co-Opted)
              </span>
              <p className="mt-0.5 font-semibold text-ink">{committee.co_opted.expert_name}</p>
              <div className="mt-2 space-y-1 border-t border-line/60 pt-2 text-11 text-ink-500">
                {committee.co_opted.reasons.map((r, rIdx) => (
                  <div key={rIdx} className="flex items-start gap-1">
                    <UserCheck className="mt-0.5 h-3 w-3 flex-shrink-0 text-sky-600" />
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
