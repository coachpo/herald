import { useEffect, useState } from "react";

export type ThemePreference = "system" | "light" | "dark";
const KEY = "herald_theme";

function storedPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function useTheme() {
  const [preference, setPreference] =
    useState<ThemePreference>(storedPreference);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.dataset.theme =
        preference === "system"
          ? media.matches
            ? "dark"
            : "light"
          : preference;
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preference]);
  const choose = (value: ThemePreference) => {
    setPreference(value);
    try {
      if (value === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, value);
    } catch {
      /* A session-only preference still works when persistence is unavailable. */
    }
  };
  return { preference, choose };
}
