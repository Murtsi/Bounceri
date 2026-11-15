import { useQuery } from "@tanstack/react-query";
import { api } from "@/api";
import { ActionBadge, LabelBadge } from "@/components/badges";
import { Skeleton } from "@/components/ui/skeleton";

function clock(iso: string) {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/**
 * Uusimmat havaitut sessiot. Uusi rivi nousee esiin omalla animaatiollaan,
 * koska rivin avain on session ID.
 */
export function LiveFeed({ onPick, limit = 8 }: { onPick: (id: string) => void; limit?: number }) {
  const { data } = useQuery({ queryKey: ["sessions", "latest", limit], queryFn: () => api.sessions(limit) });
  const rows = (data ?? [])
    .slice()
    .sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
    .slice(0, limit);
  return (
    <section aria-labelledby="latest-title">
      <header className="section-head">
        <h2 id="latest-title">Latest activity</h2>
        <p>Most recently observed sessions</p>
      </header>
      <div>
        {!data ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No traffic yet.</p>
        ) : (
          <ol className="-mx-2 flex flex-col divide-y divide-white/[0.06]" aria-live="polite">
            {rows.map((r) => (
              <li key={r.id} className="rise">
                <button
                  onClick={() => onPick(r.id)}
                  className="feed-row grid w-full items-center gap-x-3 gap-y-1 rounded-lg px-2 py-2.5 text-left outline-none hover:bg-white/[0.05] focus-visible:ring-[3px] focus-visible:ring-ring/50"
                >
                  <span className="text-xs tabular-nums text-muted-foreground">{clock(r.started_at)}</span>
                  <span className="flex min-w-0 items-center gap-2">
                    <LabelBadge label={r.label} activity={r.activity} />
                    <span className="truncate font-mono text-xs text-muted-foreground">{r.ip}</span>
                  </span>
                  <span className="feed-action"><ActionBadge action={r.action} /></span>
                  <span className="feed-reason truncate text-xs text-muted-foreground">
                    {r.reason}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
