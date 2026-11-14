export type Tone = "neutral" | "info" | "warning" | "danger" | "success";

export function formatEvaluationMetric(metric?: {
  numerator?: number;
  denominator?: number;
  value?: number | null;
  ci95_lower?: number | null;
  ci95_upper?: number | null;
}) {
  const count = (value: unknown): value is number =>
    typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
  const rate = (value: unknown): value is number =>
    typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
  const validCounts = count(metric?.numerator) && count(metric?.denominator) && metric.numerator <= metric.denominator;
  return {
    count: validCounts ? `${metric.numerator} / ${metric.denominator}` : "Not reported",
    percent:
      validCounts && metric.denominator! > 0 && rate(metric.value)
        ? `${(metric.value * 100).toFixed(2)}%`
        : "Not reported",
    interval:
      validCounts &&
      metric.denominator! > 0 &&
      rate(metric.ci95_lower) &&
      rate(metric.ci95_upper) &&
      metric.ci95_lower <= metric.ci95_upper
        ? `${(metric.ci95_lower * 100).toFixed(2)}%–${(metric.ci95_upper * 100).toFixed(2)}%`
        : "Not reported",
  };
}

export function assessmentStage(assessment: { stage?: string; kind?: string }) {
  return assessment.stage ?? assessment.kind;
}

export function capabilityState(module: string, capability?: { enabled?: boolean; implemented?: boolean }) {
  if (module !== "clean_traffic" && module !== "clean_the_traffic") {
    return { enabled: false, label: "Not implemented" };
  }
  if (!capability) return { enabled: false, label: "Status unavailable" };
  if (capability.implemented === false) return { enabled: false, label: "Not implemented" };
  return capability.enabled === true ? { enabled: true, label: "Available" } : { enabled: false, label: "Unavailable" };
}

export function sourceState(source?: { kind?: string; synthetic?: boolean } | null) {
  if (source?.synthetic === true) {
    return {
      label: source.kind === "fixture" ? "Synthetic fixture" : "Synthetic traffic",
      synthetic: true,
      tone: "warning" as Tone,
    };
  }
  if (source?.kind === "uploaded_log" && source.synthetic === false) {
    return { label: "Imported traffic", synthetic: false, tone: "info" as Tone };
  }
  if (source?.kind === "monitored_traffic" && source.synthetic === false) {
    return { label: "Real traffic", synthetic: false, tone: "info" as Tone };
  }
  return {
    label: source?.kind === "fixture" ? "Fixture · origin unverified" : "Origin unavailable",
    synthetic: false,
    tone: "neutral" as Tone,
  };
}

export function formatScore(score: unknown) {
  return typeof score === "number" && Number.isFinite(score) && score >= 0 && score <= 1
    ? `${score.toFixed(2)} / 1`
    : "Not reported";
}

export function reviewState(status?: string): {
  label: string;
  tone: Tone;
  description: string;
} {
  switch (status) {
    case "not_requested":
      return {
        label: "Not requested",
        tone: "neutral",
        description: "The local assessment is available independently of optional model review.",
      };
    case "queued":
      return {
        label: "Queued",
        tone: "info",
        description: "Review is queued. A model assessment is not available yet.",
      };
    case "running":
      return {
        label: "Running",
        tone: "info",
        description: "Review is in progress. Pending work is not a completed assessment.",
      };
    case "complete":
    case "completed":
      return {
        label: "Completed",
        tone: "success",
        description: "Inspect the recorded stages below; completion alone does not establish accuracy.",
      };
    case "failed":
      return {
        label: "Failed",
        tone: "danger",
        description: "Review failed. The local assessment has been preserved.",
      };
    case "unavailable":
      return {
        label: "Unavailable",
        tone: "warning",
        description: "Model review is unavailable. No external model conclusion is implied.",
      };
    case "deferred_budget":
      return {
        label: "Deferred · budget",
        tone: "warning",
        description: "Review was deferred by the spending limit. No completed review is implied.",
      };
    default:
      return {
        label: "Unknown review status",
        tone: "neutral",
        description: "The server has not supplied a recognised review status.",
      };
  }
}

export function dateTime(value?: string | null) {
  if (!value) return "Not reported";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not reported"
    : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function findingLabel(value?: string | null) {
  return (
    (
      {
        human: "Human-like",
        good_bot: "Verified good bot",
        bad_bot: "Suspicious automation",
        uncertain: "Uncertain",
      } as Record<string, string>
    )[value ?? ""] ??
    value ??
    "Not assessed"
  );
}
