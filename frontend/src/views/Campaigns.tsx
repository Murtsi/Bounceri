import { useQuery } from "@tanstack/react-query";
import { Network } from "lucide-react";
import type { CSSProperties } from "react";
import { type Label } from "@/api";
import { api } from "@/api";
import { LabelBadge } from "@/components/badges";
import { ListSkeleton } from "@/components/Skeletons";
import { Badge } from "@/components/ui/badge";
import { CardHeading } from "@/components/CardIcon";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default function Campaigns() {
  const { data, error } = useQuery({ queryKey: ["campaigns"], queryFn: api.campaigns });
  if (error) return <p className="text-destructive">API not responding: {String(error)}</p>;
  if (!data) return <ListSkeleton rows={4} />;
  if (data.length === 0)
    return (
      <Card>
        <CardContent className="py-6 text-center text-sm text-muted-foreground">
          No campaigns: no actor has been linked across several sessions.
        </CardContent>
      </Card>
    );
  return (
    <ul className="grid gap-4 md:grid-cols-2">
      {data.map((c, i) => (
        <li key={c.id}>
          <Card className="rise h-full" style={{ "--d": `${i * 70}ms` } as CSSProperties}>
            <CardHeader>
              <CardHeading
                Icon={Network}
                title={(c as { title?: string }).title ?? c.kind}
                description={
                  <>
                    <span className="tabular-nums">{c.size}</span> sessions · {c.kind} ·{" "}
                    <span className="font-mono text-xs">{c.id}</span>
                  </>
                }
              />
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <ul className="flex flex-wrap gap-1.5">
                {c.reasons.map((r) => (
                  <li key={r}>
                    <Badge variant="secondary" className="font-normal">
                      {r}
                    </Badge>
                  </li>
                ))}
              </ul>
              {c.labels && (
                <ul className="flex flex-wrap gap-2 text-sm">
                  {Object.entries(c.labels).map(([l, n]) => (
                    <li key={l} className="flex items-center gap-1.5">
                      <LabelBadge label={l as Label} />
                      <span className="tabular-nums text-muted-foreground">× {n}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  );
}
