import type { Delivery, Message } from "./types";

export function dateTime(value: string | null): string {
  return value
    ? new Date(value).toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
}

export const deliveryLabels: Record<Delivery["status"], string> = {
  pending: "Queued",
  sending: "Sending",
  retry: "Retry scheduled",
  sent: "Sent",
  failed: "Failed",
};

export function deliverySummary(message: Message) {
  const total = message.deliveries.length;
  const sent = message.deliveries.filter(
    (delivery) => delivery.status === "sent",
  ).length;
  const failed = message.deliveries.filter(
    (delivery) => delivery.status === "failed",
  ).length;
  const sending = message.deliveries.some(
    (delivery) => delivery.status === "sending",
  );
  const retry = message.deliveries.some(
    (delivery) => delivery.status === "retry",
  );
  return {
    total,
    sent,
    failed,
    label: failed
      ? "Needs attention"
      : total > 0 && sent === total
        ? "Delivered"
        : sending
          ? "Delivering"
          : retry
            ? "Retry scheduled"
            : total > 0
              ? "Queued"
              : "Received",
    tone: failed ? "failed" : total > 0 && sent === total ? "sent" : "pending",
  };
}
