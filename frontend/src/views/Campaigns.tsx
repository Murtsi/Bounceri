import { useQuery } from "@tanstack/react-query";
import { type Label } from "@/api";
import { api } from "@/api";
import { LabelBadge } from "@/components/badges";
import { SplashScreen } from "@/components/BouncerLogo";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Campaigns() {
  const { data, error } = useQuery({ queryKey: ["campaigns"], queryFn: api.campaigns });
  if (error) return <p className="text-destructive">API ei vastaa: {String(error)}</p>;
  if (!data) return <SplashScreen />;
  if (data.length === 0)
    return (
      <Card>
        <CardContent className="py-6 text-center text-sm text-muted-foreground">
          Ei kampanjoita: yhtään toimijaa ei ole yhdistetty usean session takaa.
        </CardContent>
      </Card>
    );
  return (
    <ul className="grid gap-4 md:grid-cols-2">
      {data.map((c) => (
        <li key={c.id}>
          <Card className="h-full">
            <CardHeader>
              <CardDescription className="font-mono text-xs">{c.id}</CardDescription>
              <CardTitle>{(c as { title?: string }).title ?? c.kind}</CardTitle>
              <CardDescription>
                <span className="tabular-nums">{c.size}</span> sessiota · {c.kind}
              </CardDescription>
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
