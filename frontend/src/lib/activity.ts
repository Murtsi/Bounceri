export function activityStatus(timestamp: string | null | undefined) {
  if (!timestamp) return { label: "No activity yet", live: false, time: null };
  const date = new Date(timestamp);
  const ageMs = Date.now() - date.getTime();
  if (!Number.isFinite(date.getTime())) return { label: "Activity time unavailable", live: false, time: null };
  const live = ageMs >= -60_000 && ageMs < 60_000;
  return {
    label: live ? "Live" : ageMs < 10 * 60_000 ? "Recent activity" : "No recent traffic",
    live,
    time: date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
  };
}
