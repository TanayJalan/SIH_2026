import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Loader2,
  Printer,
  RefreshCw,
} from "lucide-react";

import { Button } from "@/components/ui";
import { getDeficiencyReport, type DeficiencyReport } from "@/lib/api";
import { formatDateTime, humanizeEnum } from "@/lib/format";
import { cn } from "@/lib/utils";

interface DeficiencyReportPanelProps {
  applicationId: string;
  token: string;
  /**
   * Generate immediately on mount instead of waiting for the user to open
   * the panel. The review step uses this so the report is ready on arrival.
   */
  autoLoad?: boolean;
  className?: string;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function printableHtml(report: DeficiencyReport): string {
  const rows = report.items
    .map(
      (item) => `
      <tr>
        <td>${escapeHtml(item.name)}</td>
        <td>${escapeHtml(item.severity)}</td>
        <td>${escapeHtml(item.status)}</td>
        <td>${escapeHtml(item.message)}</td>
        <td>${escapeHtml(item.apH_clause)}</td>
      </tr>`,
    )
    .join("");
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Deficiency Report ${escapeHtml(report.application_no ?? report.application_id)}</title>
  <style>
    body { font-family: Georgia, serif; color: #1c1c1c; margin: 32px; line-height: 1.5; }
    h1 { font-size: 20px; text-align: center; text-transform: uppercase; letter-spacing: 0.06em; }
    .meta { font-size: 12px; color: #555; text-align: center; }
    .banner { border: 1px solid #999; padding: 10px 14px; margin: 18px 0; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 12px; }
    th, td { border: 1px solid #bbb; padding: 6px 8px; text-align: left; vertical-align: top; }
    .note { margin-top: 26px; font-size: 11px; color: #666; border-top: 1px solid #ccc; padding-top: 10px; }
  </style>
</head>
<body>
  <h1>Deficiency Report</h1>
  <p class="meta">${escapeHtml(report.application_no ?? "Application")} · ${escapeHtml(
    report.academic_year,
  )} · generated ${escapeHtml(formatDateTime(report.generated_at))}</p>
  <div class="banner"><strong>${escapeHtml(report.banner)}</strong></div>
  <p>Passed ${report.passed_count} · Failed ${report.failed_count} · Not assessed ${
    report.not_assessed_count
  } · Clause ${escapeHtml(report.apH_clause)}</p>
  <table>
    <thead>
      <tr><th>Requirement</th><th>Severity</th><th>Status</th><th>Finding</th><th>APH clause</th></tr>
    </thead>
    <tbody>${rows || '<tr><td colspan="5">No deficiencies found.</td></tr>'}</tbody>
  </table>
  <p class="note">Generated from the compliance rules configured in this prototype. Threshold values are illustrative and must be verified against the current AICTE Approval Process Handbook.</p>
</body>
</html>`;
}

function openPrintWindow(report: DeficiencyReport): void {
  const win = window.open("", "_blank", "width=900,height=700");
  if (!win) {
    return;
  }
  win.document.write(printableHtml(report));
  win.document.close();
  win.focus();
  win.print();
}

export default function DeficiencyReportPanel({
  applicationId,
  token,
  autoLoad = false,
  className,
}: DeficiencyReportPanelProps) {
  const [requested, setRequested] = useState(autoLoad);
  const [includeNotAssessed, setIncludeNotAssessed] = useState(true);

  const reportQuery = useQuery({
    queryKey: ["deficiency-report", applicationId, includeNotAssessed],
    queryFn: () => getDeficiencyReport(token, applicationId, includeNotAssessed),
    enabled: Boolean(token && applicationId && requested),
    retry: false,
  });

  if (!requested) {
    return (
      <section className={cn("rounded-input border border-line bg-paper p-4", className)}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <FileText aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-500" />
            <div>
              <h3 className="text-13 font-semibold text-ink">Deficiency Report</h3>
              <p className="mt-0.5 text-12 leading-5 text-ink-500">
                Run the current compliance rules against this application and list each gap with
                its APH clause, or confirm a Nil Deficiency.
              </p>
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setRequested(true)}>
            Generate report
          </Button>
        </div>
      </section>
    );
  }

  const report = reportQuery.data;

  return (
    <section className={cn("rounded-input border border-line bg-surface p-4", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <FileText aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-500" />
          <div>
            <h3 className="text-13 font-semibold text-ink">Deficiency Report</h3>
            <p className="mt-0.5 text-12 leading-5 text-ink-500">
              Current compliance version · {report?.apH_clause ?? "APH 2.3.3b"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-12 text-ink-700">
            <input
              type="checkbox"
              className="size-3.5 rounded border-line"
              checked={includeNotAssessed}
              onChange={(event) => setIncludeNotAssessed(event.target.checked)}
            />
            Include not assessed
          </label>
          <Button
            variant="quiet"
            size="sm"
            onClick={() => void reportQuery.refetch()}
            disabled={reportQuery.isFetching}
          >
            {reportQuery.isFetching ? (
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <RefreshCw aria-hidden="true" className="size-4" />
            )}
            Refresh
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => report && openPrintWindow(report)}
            disabled={!report}
          >
            <Printer aria-hidden="true" className="size-4" />
            Print
          </Button>
        </div>
      </div>

      {reportQuery.isPending ? (
        <p className="mt-3 flex items-center gap-2 text-13 text-ink-500">
          <Loader2 aria-hidden="true" className="size-4 animate-spin" />
          Evaluating the compliance rules…
        </p>
      ) : reportQuery.isError ? (
        <p className="mt-3 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          The Deficiency Report could not be generated.
        </p>
      ) : report ? (
        <div className="mt-3 space-y-3">
          <div
            className={cn(
              "flex items-start gap-2.5 rounded-input border p-3",
              report.nil_deficiency
                ? "border-ok bg-ok-soft text-ok-strong"
                : "border-watch bg-watch-soft text-watch-strong",
            )}
          >
            {report.nil_deficiency ? (
              <CheckCircle2 aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            ) : (
              <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            )}
            <div>
              <p className="text-13 font-semibold">{report.banner}</p>
              <p className="mt-0.5 text-12 leading-5">
                {report.passed_count} passed · {report.failed_count} failed ·{" "}
                {report.not_assessed_count} not assessed · generated{" "}
                {formatDateTime(report.generated_at)}
              </p>
            </div>
          </div>

          {report.items.length === 0 ? (
            <p className="text-13 text-ink-700">
              No deficiency is recorded against the current rules.
            </p>
          ) : (
            <ul className="space-y-2">
              {report.items.map((item) => (
                <li key={item.code} className="rounded-input border border-line bg-paper p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "rounded-pill px-2 py-0.5 text-12 font-medium",
                        item.status === "FAIL"
                          ? "bg-breach-soft text-breach-strong"
                          : "bg-neutral-soft text-neutral-strong",
                      )}
                    >
                      {humanizeEnum(item.status)}
                    </span>
                    <span className="text-12 font-medium text-ink">{humanizeEnum(item.severity)}</span>
                    <span className="rounded-pill border border-line bg-surface px-2 py-0.5 text-12 text-ink-700">
                      {item.apH_clause}
                    </span>
                    {item.needs_verification ? (
                      <span className="rounded-pill bg-watch-soft px-2 py-0.5 text-12 text-watch-strong">
                        Needs verification
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-13 font-medium text-ink">{item.name}</p>
                  <p className="mt-0.5 text-12 leading-5 text-ink-700">{item.message}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </section>
  );
}
