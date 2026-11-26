import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { formatEvaluationMetric } from "@/investigationPresentation";
import { investigationApi } from "@/investigationsApi";
import { cn } from "@/lib/utils";

const repository = "https://github.com/Murtsi/Bounceri";
const factClass = "grid gap-1 py-2 sm:grid-cols-[minmax(8rem,1fr)_2fr] sm:gap-4";
const linkClass = "text-xs font-medium text-blue-800 underline underline-offset-4 dark:text-blue-200";

export default function EvaluationPanel({ className }: { className?: string }) {
  const query = useQuery({
    queryKey: ["evaluation"],
    queryFn: investigationApi.evaluation,
    retry: false,
    refetchInterval: 30_000,
  });
  const evaluation = query.data;
  const freezeCommit = evaluation?.detector?.freeze_commit;
  const count = (value: unknown) =>
    typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : "Not reported";
  return (
    <section
      aria-labelledby="evaluation-title"
      className={cn("glass min-w-0 rounded-2xl border border-border p-5", className)}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="evaluation-title" className="font-semibold">
          Detector evaluation
        </h2>
        <button
          onClick={() => void query.refetch()}
          className="rounded-md border border-input px-3 py-1.5 text-xs font-medium hover:bg-accent"
          disabled={query.isFetching}
        >
          Refresh evaluation
        </button>
      </div>
      {query.isPending && (
        <p role="status" className="mt-3 text-sm text-muted-foreground">Loading published evaluation…</p>
      )}
      {query.error && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          Evaluation could not be loaded. {query.error.message}
        </p>
      )}
      {!query.error && evaluation?.available !== true && !query.isPending && (
        <div className="mt-3 text-sm text-muted-foreground">
          <p className="font-medium">Evaluation not published</p>
          <p className="mt-1">
            {evaluation?.reason ?? "No evaluation result has been supplied."} This is not a measured zero-error result.
          </p>
        </div>
      )}
      {!query.error && evaluation?.available === true && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-status-warning/30 bg-status-warning/5 text-status-warning">
              {evaluation.synthetic === true ? "Synthetic benchmark" : "Source status unavailable"}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {evaluation.dataset?.split === "reserved_known_templates"
                ? "Reserved known-template runs"
                : (evaluation.dataset?.split ?? "Split not reported")}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {count(evaluation.dataset?.n_sessions)} sessions · {count(evaluation.dataset?.n_runs)} runs ·{" "}
            {count(evaluation.dataset?.n_known)} known · {count(evaluation.dataset?.n_unknown)} unknown
          </p>
          <dl className="grid gap-4 md:grid-cols-3">
            {(
              [
                ["Bad bot precision", evaluation.metrics?.bad_bot_precision],
                ["Simulated human false positives", evaluation.metrics?.human_false_positive_rate],
                ["Uncertain share", evaluation.metrics?.uncertain_share],
              ] as const
            ).map(([label, metric]) => {
              const value = formatEvaluationMetric(metric);
              return (
                <div key={label} className="min-w-0 border-t border-border pt-3">
                  <dt className="text-sm font-medium">{label}</dt>
                  <dd className="mt-1 font-mono text-lg tabular-nums">{value.count}</dd>
                  <dd className="mt-1 text-xs text-muted-foreground">
                    {value.percent} · 95% interval: {value.interval}
                  </dd>
                </div>
              );
            })}
          </dl>
          <p className="text-xs leading-relaxed text-muted-foreground">
            This synthetic benchmark does not establish real-human performance or an independent hidden-attack result.
            Reserved known templates are not a genuinely hidden attack.
          </p>
          {Array.isArray(evaluation.limitations) && evaluation.limitations.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-xs leading-relaxed text-muted-foreground">
              {evaluation.limitations.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          )}
          {Array.isArray(evaluation.unavailable) && evaluation.unavailable.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Unavailable: {evaluation.unavailable.map((item) => item.replaceAll("_", " ")).join("; ")}.
            </p>
          )}
          <details>
            <summary className="cursor-pointer text-xs font-medium text-blue-800 dark:text-blue-200">
              Dataset and detector provenance
            </summary>
            <dl className="mt-2 divide-y divide-border text-sm">
              <div className={factClass}>
                <dt className="text-muted-foreground">Dataset</dt>
                <dd className="min-w-0 break-words">{evaluation.dataset?.id ?? "Not reported"}</dd>
              </div>
              <div className={factClass}>
                <dt className="text-muted-foreground">Detector version</dt>
                <dd className="min-w-0 break-words">{evaluation.detector?.model_version ?? "Not reported"}</dd>
              </div>
              <div className={factClass}>
                <dt className="text-muted-foreground">Frozen benchmark commit</dt>
                <dd className="min-w-0 break-all font-mono text-xs">
                  {freezeCommit && /^[a-f0-9]{40}$/.test(freezeCommit) ? (
                    <a href={`${repository}/commit/${freezeCommit}`} className={linkClass}>{freezeCommit}</a>
                  ) : "Not reported"}
                </dd>
              </div>
            </dl>
          </details>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            <a href={`${repository}/blob/main/docs/EVALUATION.md`} className={linkClass}>Read the benchmark method</a>
            <a href="/api/evaluation" className={linkClass}>Read evaluation JSON</a>
          </div>
        </div>
      )}
    </section>
  );
}
