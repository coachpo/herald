import { useEffect, useMemo, useState } from "react";

import { CheckIcon, LaptopIcon, MoonIcon, SunIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type Theme = "system" | "light" | "dark";

const STORAGE_KEY = "herald_theme";

function applyTheme(t: Theme) {
  const root = document.documentElement;
  if (t === "light" || t === "dark") {
    root.setAttribute("data-theme", t);
  } else {
    root.removeAttribute("data-theme");
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      if (v === "light" || v === "dark") return v;
      return "system";
    } catch {
      return "system";
    }
  });

  useEffect(() => {
    applyTheme(theme);
    try {
      if (theme === "system") {
        localStorage.removeItem(STORAGE_KEY);
      } else {
        localStorage.setItem(STORAGE_KEY, theme);
      }
    } catch {
      return;
    }
  }, [theme]);

  const label = useMemo(() => {
    if (theme === "system") return "Theme: System";
    if (theme === "light") return "Theme: Light";
    return "Theme: Dark";
  }, [theme]);

  const icon = useMemo(() => {
    if (theme === "system") return <LaptopIcon />;
    if (theme === "light") return <SunIcon />;
    return <MoonIcon />;
  }, [theme]);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" aria-label={label} title={label}>
          {icon}
          {theme === "system" ? "System" : theme === "light" ? "Light" : "Dark"}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        <DropdownMenuSeparator />

        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault();
            setTheme("system");
          }}
        >
          <LaptopIcon />
          System
          {theme === "system" && <CheckIcon className="ml-auto" />}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault();
            setTheme("light");
          }}
        >
          <SunIcon />
          Light
          {theme === "light" && <CheckIcon className="ml-auto" />}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault();
            setTheme("dark");
          }}
        >
          <MoonIcon />
          Dark
          {theme === "dark" && <CheckIcon className="ml-auto" />}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
