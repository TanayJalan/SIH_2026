import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FilePlus2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Breadcrumbs from "../components/Breadcrumbs";
import PageHeader from "../components/PageHeader";
import { Button, Input, Select, useToast } from "../components/ui";
import { currentAcademicYear } from "../lib/application";
import {
  ApiError,
  createApplication,
  type ApplicationType,
} from "../lib/api";

const APPLICATION_TYPE_OPTIONS = [
  { value: "NEW", label: "New approval" },
  { value: "EXTENSION", label: "Extension of approval" },
];

export default function NewApplicationPage() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [applicationType, setApplicationType] = useState<ApplicationType>("NEW");
  const [academicYear, setAcademicYear] = useState(currentAcademicYear);
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createApplication(token ?? "", {
        application_type: applicationType,
        academic_year: academicYear,
      }),
    onSuccess: (application) => {
      void queryClient.invalidateQueries({ queryKey: ["applications"] });
      toast({
        title: "Draft created",
        description: "Complete the wizard and submit when every required item is ready.",
        variant: "success",
      });
      navigate(`/applications/${application.id}/edit`, { replace: true });
    },
    onError: (mutationError) => {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "The draft could not be created.",
      );
    },
  });

  if (!user) {
    return null;
  }

  const submit = () => {
    setError(null);
    if (!/^\d{4}-\d{2}$/.test(academicYear)) {
      setError("Academic year must use the format 2026-27.");
      return;
    }
    createMutation.mutate();
  };

  return (
    <>
      <Breadcrumbs
        items={[
          { label: "My applications", to: "/applications" },
          { label: "New application" },
        ]}
      />
      <PageHeader
        eyebrow="Institution workspace"
        title="Start a new application"
        description="Create a draft for the AICTE approval cycle. You can save each step and return before submitting."
        actions={
          <Button asChild variant="secondary" size="sm">
            <Link to="/applications">
              <ArrowLeft aria-hidden="true" className="size-4" />
              Back to applications
            </Link>
          </Button>
        }
      />

      <div className="grid max-w-5xl grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.75fr)]">
        <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-input bg-saffron-50 text-saffron-strong">
              <FilePlus2 aria-hidden="true" className="size-5" />
            </span>
            <div>
              <h2 className="font-serif text-20 font-semibold text-ink">Draft details</h2>
              <p className="mt-0.5 text-12 text-ink-500">
                Choose the application type and academic year.
              </p>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <Select
              label="Application type"
              options={APPLICATION_TYPE_OPTIONS}
              value={applicationType}
              onValueChange={(value) => setApplicationType(value as ApplicationType)}
              required
            />
            <Input
              label="Academic year"
              value={academicYear}
              onChange={(event) => setAcademicYear(event.target.value)}
              placeholder="2026-27"
              hint="Use the two-year format, for example 2026-27."
              required
            />
            {error ? (
              <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong" role="alert">
                {error}
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
              <Button onClick={submit} disabled={createMutation.isPending}>
                <FilePlus2 aria-hidden="true" className="size-4" />
                {createMutation.isPending ? "Creating draft…" : "Create draft"}
              </Button>
              <p className="text-12 text-ink-500">
                Required documents depend on the application type.
              </p>
            </div>
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-panel border border-line bg-surface p-5">
            <h2 className="text-14 font-semibold text-ink">What happens next</h2>
            <ol className="mt-3 space-y-3 text-13 leading-5 text-ink-700">
              <li>
                <span className="font-medium text-ink">1. Complete the sections.</span>{" "}
                Profile, infrastructure, faculty, finance, accreditation and the mandatory
                disclosure are validated before submission.
              </li>
              <li>
                <span className="font-medium text-ink">2. Add programmes.</span> Record the
                intake, faculty and laboratory counts for each programme requested.
              </li>
              <li>
                <span className="font-medium text-ink">3. Upload documents.</span> The checklist
                is driven by the selected application type and shows every required upload.
              </li>
              <li>
                <span className="font-medium text-ink">4. Review and submit.</span> The server
                blocks submission and lists anything still missing.
              </li>
            </ol>
          </section>
          <section className="rounded-panel border border-watch bg-watch-soft p-5">
            <h2 className="text-13 font-semibold text-watch-strong">Demo data notice</h2>
            <p className="mt-2 text-12 leading-5 text-watch-strong">
              Required document rules and SLA durations in this prototype are illustrative.
              Verify them against the current AICTE Approval Process Handbook before using this
              workflow for a real application.
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}
