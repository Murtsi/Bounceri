import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/** Lasikortti, jonka sisältö latautuu: otsikko + annettu runko. */
function SkeletonCard({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <Card className={className}>
      <CardHeader>
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-1 h-3 w-28" />
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** Yleiskuvan muotoinen latausnäkymä: sama asettelu kuin valmiina, ei hyppimistä. */
export function OverviewSkeleton() {
  return (
    <div role="status" aria-label="Loading overview" className="flex flex-col gap-4">
      <Card className="p-6">
        <Skeleton className="h-5 w-24 rounded-full" />
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </Card>
      <div className="flex flex-wrap gap-4">
        <SkeletonCard className="min-w-0 flex-[999_1_560px]">
          <Skeleton className="mb-4 h-8 w-20" />
          <div className="flex h-48 items-end gap-[3px]">
            {Array.from({ length: 28 }, (_, i) => (
              <Skeleton
                key={i}
                className="flex-1 rounded-b-none rounded-t-[4px]"
                style={{ height: `${25 + ((i * 37) % 70)}%`, animationDelay: `${i * 30}ms` }}
              />
            ))}
          </div>
        </SkeletonCard>
        <SkeletonCard className="min-w-0 flex-[1_1_300px]">
          <Skeleton className="mb-3 h-12 w-28" />
          <Skeleton className="h-7 w-full rounded-full" />
        </SkeletonCard>
      </div>
      <ListSkeleton rows={3} />
    </div>
  );
}

export function ListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <SkeletonCard>
      <div role="status" aria-label="Loading" className="flex flex-col gap-3">
        {Array.from({ length: rows }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full" style={{ animationDelay: `${i * 80}ms` }} />
        ))}
      </div>
    </SkeletonCard>
  );
}
