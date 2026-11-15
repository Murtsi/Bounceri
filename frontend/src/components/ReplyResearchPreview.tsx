import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";

interface Rate {
  numerator: number;
  denominator: number;
  value: number | null;
  ci95_lower: number | null;
  ci95_upper: number | null;
}

interface Split {
  n: number;
  targeted: number;
  controls: number;
  precision: Rate;
  recall: Rate;
  false_positive_rate: Rate;
  abstention_rate: Rate;
}

interface ReplyResearch {
  schema_version: number;
  available: boolean;
  scope: string;
  source: { title: string; authors: string[]; doi: string; url: string; license: string; file_sha256: string };
  dataset: { raw_rows: number; unique_posts: number; targeted: number; controls: number; duplicate_id_rows: number; numeric_features: number };
  baseline: { feature: string; direction: string; threshold: number; selection: string };
  splits: Record<"train" | "validation" | "test", Split>;
  limitations: string[];
}

async function loadResearch(): Promise<ReplyResearch> {
  const response = await fetch("/api/evaluation/social-replies");
  if (!response.ok) throw new Error("Research report unavailable");
  const report = await response.json() as ReplyResearch;
  if (report.schema_version !== 1 || report.available !== true || report.scope !== "historical_tweet_targeting_research") {
    throw new Error("Research report unavailable");
  }
  return report;
}

const count = (value: number) => value.toLocaleString("en-GB");
const percent = (value: number | null) => typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "Unavailable";

function ResearchFigure({ title, rate }: { title: string; rate: Rate }) {
  return (
    <div className="metric-figure">
      <dt>{title}</dt>
      <dd>
        <span className="metric-value">{percent(rate.value)}</span>
        <span className="metric-note">{count(rate.numerator)} / {count(rate.denominator)} posts</span>
        <span className="metric-note">95% CI {percent(rate.ci95_lower)}–{percent(rate.ci95_upper)}</span>
      </dd>
    </div>
  );
}

export default function ReplyResearchPreview() {
  const { data, error, isPending } = useQuery({
    queryKey: ["reply-research-preview"],
    queryFn: loadResearch,
    staleTime: Infinity,
    refetchInterval: false,
    refetchOnWindowFocus: false,
    retry: false,
  });

  return (
    <section className="overview-section border-t pt-8" aria-labelledby="reply-research-title">
      <header className="section-head">
        <h2 id="reply-research-title">Reply attack research preview</h2>
        <p>Historical tweet-targeting benchmark — research preview</p>
      </header>
      {isPending ? (
        <p role="status" className="text-sm text-muted-foreground">Loading historical research report…</p>
      ) : error || !data ? (
        <p role="status" className="text-sm text-destructive">Research preview unavailable. No research result can be shown.</p>
      ) : (
        <div className="flex flex-col gap-5">
          <p className="text-sm leading-relaxed text-muted-foreground">
            A one-feature baseline estimates which historical posts met the dataset’s targeting rule: at least five replies from influence-operation accounts.
            Selected controls also received at least five replies. These are post-level research labels, not account identities or intent verdicts.
          </p>
          <div className="flex items-start gap-3 rounded-xl border border-[rgba(250,178,25,0.22)] bg-[rgba(250,178,25,0.05)] px-4 py-3 text-sm" role="note">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-status-warning" aria-hidden="true" />
            <p><strong>Independence unverified.</strong> Actor and campaign IDs are unavailable, so related activity may cross the post-level splits. These results do not establish live social detection or native bot-detection quality.</p>
          </div>
          <div>
            <p className="mb-3 text-sm font-medium">Held-out test · {count(data.splits.test.n)} posts · {count(data.splits.test.targeted)} targeted · {count(data.splits.test.controls)} selected controls</p>
            <dl className="metric-strip">
              <ResearchFigure title="Targeted-post precision" rate={data.splits.test.precision} />
              <ResearchFigure title="Targeted-post recall" rate={data.splits.test.recall} />
              <ResearchFigure title="Selected-control false-positive rate" rate={data.splits.test.false_positive_rate} />
            </dl>
            <p className="mt-3 text-sm text-muted-foreground">
              Abstention: {percent(data.splits.test.abstention_rate.value)} ({count(data.splits.test.abstention_rate.numerator)} / {count(data.splits.test.abstention_rate.denominator)} test posts).
              {" "}Rates and intervals describe this selected dataset; post dependence is not accounted for.
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            {count(data.dataset.unique_posts)} unique posts: {count(data.dataset.targeted)} targeted and {count(data.dataset.controls)} selected controls.
            {" "}A frozen tweet-ID hash assigns 70% / 15% / 15% to train / validation / test before tuning. The threshold is selected on training data only.
          </p>
          <details className="text-sm text-muted-foreground">
            <summary className="cursor-pointer text-foreground">Method, split counts and research limitations</summary>
            <div className="mt-4 flex flex-col gap-4 leading-relaxed">
              <p>Decision stump: <code>{data.baseline.feature}</code> {data.baseline.direction} {data.baseline.threshold}. Selection: <code>{data.baseline.selection}</code>.</p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs tabular-nums">
                  <caption className="mb-2 text-left">Post-level partitions · threshold fitted only on train</caption>
                  <thead><tr><th className="py-2 pr-4">Split</th><th className="pr-4">Posts</th><th className="pr-4">Targeted</th><th>Controls</th></tr></thead>
                  <tbody>{(["train", "validation", "test"] as const).map((name) => (
                    <tr className="border-t" key={name}><th className="py-2 pr-4 font-normal">{name}</th><td className="pr-4">{count(data.splits[name].n)}</td><td className="pr-4">{count(data.splits[name].targeted)}</td><td>{count(data.splits[name].controls)}</td></tr>
                  ))}</tbody>
                </table>
              </div>
              <ul className="list-disc space-y-2 pl-5">{data.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
              <p>Derived changes: first-row deduplication removed {count(data.dataset.duplicate_id_rows)} duplicate-ID rows from {count(data.dataset.raw_rows)} source rows; {count(data.dataset.numeric_features)} numeric features were available. This preview uses one feature and publishes aggregate results only.</p>
              <p className="break-all text-xs">Source file SHA-256: <code>{data.source.file_sha256}</code></p>
            </div>
          </details>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Source: <a className="underline underline-offset-4 hover:text-foreground" href={data.source.url} target="_blank" rel="noreferrer">{data.source.title}</a> · {data.source.authors.join(", ")} · {data.source.license} · DOI {data.source.doi}.
            {" "}Derived benchmark and display by Bounceri.
          </p>
        </div>
      )}
    </section>
  );
}
