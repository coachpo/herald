export function priorityBadgeClass(priority: number): string {
  if (priority <= 1) return "border-border bg-muted text-muted-foreground";
  if (priority === 2) return "border-info/20 bg-info/10 text-info";
  if (priority === 4) return "border-warning/20 bg-warning/10 text-warning";
  if (priority >= 5) return "border-destructive/20 bg-destructive/10 text-destructive";
  return "border-border bg-card text-foreground";
}
