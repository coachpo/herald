import type { ReactNode } from "react";
import { Icon } from "./Icon";

interface FeedbackProps {
  readonly children: ReactNode;
  readonly tone?: "error" | "success" | "info";
  readonly onRetry?: () => void;
}

export function Feedback({ children, tone = "info", onRetry }: FeedbackProps) {
  return (
    <div
      className={`feedback ${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon
        name={
          tone === "error" ? "alert" : tone === "success" ? "check" : "clock"
        }
      />
      <div>{children}</div>
      {onRetry && (
        <button type="button" className="ghost" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
