import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Printer,
  RefreshCw,
  Scale,
} from "lucide-react";

import { Button } from "@/components/ui";
import {
  downloadDeficiencyReportPdf,
  getDeficiencyReport,
  type DeficiencyReport,
} from "@/lib/api";
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
        <td>${escapeHtml(item.name)}${
          item.illustrative ? " <em>(illustrative, not an AICTE norm)</em>" : ""
        }</td>
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
  } · Mandatory failures ${report.mandatory_failed_count} · Mandatory unassessed ${
    report.mandatory_missing_count
  }</p>
  <table>
    <thead>
      <tr><th>Requirement</th><th>Severity</th><th>Status</th><th>Finding</th><th>APH clause</th></tr>
    </thead>
    <tbody>${rows || '<tr><td colspan="5">No deficiencies found.</td></tr>'}</tbody>
  </table>
  <p class="note">A Nil Deficiency result requires every mandatory rule to pass. Rows marked illustrative are project-only demo thresholds, not AICTE norms. Threshold values are configurable and must be verified against the current AICTE Approval Process Handbook.</p>
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
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const reportQuery = useQuery({
    queryKey: ["deficiency-report", applicationId, includeNotAssessed],
    queryFn: () => getDeficiencyReport(token, applicationId, includeNotAssessed),
    enabled: Boolean(token && applicationId && requested),
    retry: false,
  });

  async function downloadPdf() {
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadDeficiencyReportPdf(token, applicationId);
    } catch {
      setDownloadError("The PDF could not be generated.");
    } finally {
      setDownloading(false);
    }
  }

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
          <Button
            variant="primary"
            size="sm"
            onClick={() => void downloadPdf()}
            disabled={!report || downloading}
          >
            {downloading ? (
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <Download aria-hidden="true" className="size-4" />
            )}
            Download PDF
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
                {report.not_assessed_count} not assessed ·{" "}
                {report.mandatory_failed_count} mandatory failures ·{" "}
                {report.mandatory_missing_count} mandatory unassessed · generated{" "}
                {formatDateTime(report.generated_at)}
              </p>
            </div>
          </div>

          {downloadError ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {downloadError}
            </p>
          ) : null}

          {report.illustrative_failed_count > 0 ? (
            <p className="rounded-input border border-line bg-neutral-soft p-2.5 text-12 leading-5 text-ink-700">
              {report.illustrative_failed_count} illustrative project threshold
              {report.illustrative_failed_count === 1 ? "" : "s"} listed below{" "}
              {report.illustrative_failed_count === 1 ? "is" : "are"} for information
              only and cannot block a Nil Deficiency result.
            </p>
          ) : null}

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
                    {!item.mandatory ? (
                      <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-12 text-ink-700">
                        Advisory
                      </span>
                    ) : null}
                    {item.illustrative ? (
                      <span className="rounded-pill bg-watch-soft px-2 py-0.5 text-12 text-watch-strong">
                        Illustrative, not an AICTE norm
                      </span>
                    ) : null}
                    {item.needs_verification ? (
                      <span className="rounded-pill bg-watch-soft px-2 py-0.5 text-12 text-watch-strong">
                        Needs verification
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-13 font-medium text-ink">{item.name}</p>
                  <p className="mt-0.5 text-12 leading-5 text-ink-700">{item.message}</p>
                  {item.penal_action_suggestions.length > 0 ? (
                    <div className="mt-2 rounded-input border border-line bg-surface p-2.5">
                      <p className="flex items-center gap-1.5 text-12 font-medium text-ink">
                        <Scale aria-hidden="true" className="size-3.5 text-ink-500" />
                        Suggested action under APH 7.3
                      </p>
                      <ul className="mt-1 space-y-1 text-12 leading-5 text-ink-700">
                        {item.penal_action_suggestions.map((suggestion) => (
                          <li key={`${item.code}-${suggestion.violation_code}`}>
                            {suggestion.action_label} · {suggestion.violation_code} (
                            {suggestion.apH_clause})
                          </li>
                        ))}
                      </ul>
                      <p className="mt-1 text-12 text-ink-500">
                        A show-cause notice, hearing and speaking order are mandatory before
                        any action is imposed.
                      </p>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </section>
  );
}
