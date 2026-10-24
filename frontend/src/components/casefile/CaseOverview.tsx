import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

import { StatusPill } from "@/components/ui";
import type { ApplicationDetail, ComplianceRulePreview } from "@/lib/api";
import { formatDate, formatDateTime, humanizeEnum } from "@/lib/format";

type Fact = { label: string; value: ReactNode };

function Fact({ label, value }: Fact) {
  return (
    <div className="min-w-0">
      <dt className="text-12 font-medium text-ink-500">{label}</dt>
      <dd className="mt-1 min-w-0 text-14 text-ink">{value}</dd>
    </div>
  );
}

function notRecorded(value: ReactNode): ReactNode {
  return value ?? "Not recorded";
}

function money(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `₹${value.toLocaleString("en-IN")}`;
}

export default function CaseOverview({
  application,
  rules,
}: {
  application: ApplicationDetail;
  rules: ComplianceRulePreview[];
}) {
  const data = application.data;
  const profile = data.institution_profile;
  const infrastructure = data.infrastructure;
  const faculty = data.faculty;
  const finance = data.finance;
  const accreditation = data.accreditation;

  const facts: Fact[] = [
    { label: "Institution", value: application.institution.name },
    {
      label: "Location",
      value: `${application.institution.state} · ${application.institution.region}`,
    },
    { label: "Application type", value: humanizeEnum(application.application_type) },
    { label: "Academic year", value: application.academic_year },
    { label: "Reference", value: application.reference ?? "—" },
    { label: "Submitted", value: formatDate(application.submitted_at) },
    { label: "SLA due", value: formatDate(application.sla_due_at) },
    { label: "Stage entered", value: formatDateTime(application.stage_entered_at) },
    {
      label: "Assigned officer",
      value: application.assigned_officer
        ? `${application.assigned_officer.name} · ${application.assigned_officer.email}`
        : "Not assigned",
    },
    { label: "Head of institution", value: notRecorded(profile?.head_name) },
    {
      label: "Contact",
      value:
        profile?.contact_email || profile?.contact_phone
          ? [profile?.contact_email, profile?.contact_phone].filter(Boolean).join(" · ")
          : "Not recorded",
    },
    {
      label: "Address",
      value:
        [
          profile?.address_line1,
          profile?.address_line2,
          profile?.city,
          profile?.state,
          profile?.pin_code,
        ]
          .filter(Boolean)
          .join(", ") || "Not recorded",
    },
    {
      label: "Infrastructure",
      value: infrastructure
        ? `${infrastructure.land_area ?? "—"} sq m land · ${infrastructure.built_up_area ?? "—"} sq m built-up · ${infrastructure.labs ?? "—"} labs`
        : "Not recorded",
    },
    {
      label: "Library and hostel",
      value: infrastructure
        ? `${infrastructure.library ?? "—"} volumes · ${infrastructure.hostel ?? "—"} hostel capacity`
        : "Not recorded",
    },
    {
      label: "Faculty",
      value: faculty
        ? `${faculty.total ?? "—"} total · ${faculty.professors ?? "—"} prof · ${faculty.associate_professors ?? "—"} assoc · ${faculty.assistant_professors ?? "—"} asst`
        : "Not recorded",
    },
    {
      label: "Declared ratios",
      value: faculty
        ? `${faculty.student_faculty_ratio ?? "—"} students/faculty · ${faculty.phd_faculty_ratio ?? "—"}% with PhD`
        : "Not recorded",
    },
    {
      label: "Fee structure",
      value: finance
        ? `${money(finance.tuition_fee)} tuition · ${money(finance.development_fee)} development · ${money(finance.other_fees)} other`
        : "Not recorded",
    },
    {
      label: "Declared balance",
      value: finance ? money(finance.balance) : "Not recorded",
    },
    {
      label: "Accreditation",
      value: accreditation
        ? `NAAC ${accreditation.naac_grade ?? "—"} · NBA ${humanizeEnum(accreditation.nba_status ?? "NOT_ACCREDITED")}`
        : "Not recorded",
    },
    {
      label: "Mandatory disclosure",
      value: data.mandatory_disclosure_url ? (
        <a
          href={data.mandatory_disclosure_url}
          target="_blank"
          rel="noreferrer"
          className="break-all text-info-strong underline-offset-4 hover:underline"
        >
          {data.mandatory_disclosure_url}
        </a>
      ) : (
        "Not recorded"
      ),
    },
    ...(application.decision
      ? [
          {
            label: "Decision outcome",
            value: humanizeEnum(application.decision.outcome),
          },
          {
            label: "Decided by",
            value: `${application.decision.decided_by_name} · ${formatDateTime(application.decision.decided_at)}`,
          },
          ...(application.decision.conditions
            ? [{ label: "Conditions", value: application.decision.conditions }]
            : []),
        ]
      : []),
  ];

  const failedRules = rules.filter((rule) => rule.status === "FAIL");

  return (
    <div className="space-y-6">
      {failedRules.length > 0 ? (
        <section
          aria-label="Anomaly flags"
          className="rounded-input border border-watch bg-watch-soft p-4"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle aria-hidden="true" className="size-4 text-watch-strong" />
            <h3 className="text-13 font-semibold text-watch-strong">
              Anomaly flags ({failedRules.length})
            </h3>
          </div>
          <ul className="mt-2 space-y-1 text-13 text-ink-700">
            {failedRules.map((rule) => (
              <li key={rule.code} className="flex flex-wrap items-center gap-2">
                <StatusPill
                  status={rule.severity === "LOW" ? "watch" : "breach"}
                >
                  {rule.severity}
                </StatusPill>
                {rule.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <h2 className="font-serif text-20 font-semibold text-ink">Case facts</h2>
        <dl className="mt-5 grid grid-cols-1 gap-x-6 gap-y-5 border-t border-line pt-5 sm:grid-cols-2">
          {facts.map((fact) => (
            <Fact key={fact.label} {...fact} />
          ))}
        </dl>
      </section>

      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2 className="font-serif text-20 font-semibold text-ink">Programmes</h2>
          <span className="rounded-pill bg-paper px-2.5 py-1 text-12 text-ink-700">
            {application.programs.length} recorded
          </span>
        </div>
        {application.programs.length === 0 ? (
          <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
            No programmes recorded on this application.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-panel border border-line">
            <table className="w-full min-w-[480px] text-left text-13">
              <caption className="sr-only">Programmes applied for</caption>
              <thead>
                <tr className="border-b border-line bg-paper">
                  <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">
                    Programme
                  </th>
                  <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">
                    Level
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">
                    Intake
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">
                    Faculty
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">
                    Labs
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {application.programs.map((program) => (
                  <tr key={program.id}>
                    <td className="px-4 py-2.5 font-medium text-ink">
                      {program.program_name}
                    </td>
                    <td className="px-4 py-2.5 text-ink-700">{program.level}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-ink-700">
                      {program.intake}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-ink-700">
                      {program.faculty_count}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-ink-700">
                      {program.lab_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
