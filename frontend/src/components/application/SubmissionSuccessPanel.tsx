import { ArrowRight, CalendarClock, CheckCircle2, FileSearch, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui";
import type { ApplicationSubmission } from "@/lib/api";
import { formatDate, formatDateTime, shortId } from "@/lib/format";

interface SubmissionSuccessPanelProps {
  submission: ApplicationSubmission;
}

const NEXT_STEPS = [
  {
    title: "Document verification",
    description:
      "A scrutiny officer checks the uploaded versions and may flag a document for replacement.",
  },
  {
    title: "Scrutiny and deficiencies",
    description:
      "The regional office reviews the declared data. If a deficiency is raised, respond from the application record.",
  },
  {
    title: "Inspection, where required",
    description:
      "An inspection committee may be scheduled to verify infrastructure and faculty claims on campus.",
  },
  {
    title: "Decision",
    description:
      "The competent authority records the approval decision. Track the SLA and alerts in the application.",
  },
];

export default function SubmissionSuccessPanel({ submission }: SubmissionSuccessPanelProps) {
  const application = submission.application;
  const reference = application.reference ?? `Application ${shortId(application.id)}`;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5">
      <section className="rounded-panel border border-ok bg-surface p-6 sm:p-8">
        <span className="flex size-12 items-center justify-center rounded-full bg-ok-soft text-ok-strong">
          <CheckCircle2 aria-hidden="true" className="size-6" />
        </span>
        <p className="mt-5 text-12 font-semibold uppercase tracking-[0.14em] text-ok-strong">
          Submission complete
        </p>
        <h1 className="mt-2 font-serif text-30 font-semibold text-ink">
          Application submitted
        </h1>
        <p className="mt-2 max-w-xl text-14 leading-6 text-ink-700">
          {application.institution.name} has submitted its{" "}
          {application.application_type.toLowerCase()} application for {application.academic_year}.
          The approval workflow has started.
        </p>

        <dl className="mt-6 grid grid-cols-1 gap-4 rounded-input border border-line bg-paper p-4 sm:grid-cols-3">
          <div>
            <dt className="text-11 font-medium uppercase tracking-wide text-ink-500">
              Application ID
            </dt>
            <dd className="mt-1 break-all text-13 font-semibold text-ink">{reference}</dd>
          </div>
          <div>
            <dt className="text-11 font-medium uppercase tracking-wide text-ink-500">
              Submitted
            </dt>
            <dd className="mt-1 text-13 text-ink">{formatDateTime(submission.submitted_at)}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-1 text-11 font-medium uppercase tracking-wide text-ink-500">
              <CalendarClock aria-hidden="true" className="size-3" />
              Expected decision
            </dt>
            <dd className="mt-1 text-13 font-semibold text-ink">
              {formatDate(submission.sla_due_at)}
            </dd>
          </div>
        </dl>

        <p className="mt-3 flex items-start gap-1.5 text-11 leading-4 text-ink-500">
          <ShieldCheck aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          The expected decision date is calculated from the configured application-stage SLA. It
          is an illustrative target, not a guaranteed decision date.
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button asChild>
            <Link to={`/applications/${application.id}`}>
              Open application
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </Button>
          <Button asChild variant="secondary">
            <Link to="/applications">Back to applications</Link>
          </Button>
        </div>
      </section>

      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <div className="flex items-center gap-2">
          <FileSearch aria-hidden="true" className="size-4 text-ink-500" />
          <h2 className="text-14 font-semibold text-ink">What happens next</h2>
        </div>
        <ol className="mt-4 space-y-4">
          {NEXT_STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-3">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-paper text-11 font-semibold tabular-nums text-ink-700">
                {index + 1}
              </span>
              <div>
                <p className="text-13 font-medium text-ink">{step.title}</p>
                <p className="mt-0.5 text-12 leading-5 text-ink-500">{step.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
