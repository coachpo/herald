import type { ThemePreference } from "../hooks/useTheme";

interface ThemePickerProps {
  readonly value: ThemePreference;
  readonly onChange: (value: ThemePreference) => void;
}

export function ThemePicker({ value, onChange }: ThemePickerProps) {
  return (
    <label className="theme-picker">
      <span>Appearance</span>
      <select
        aria-label="Appearance"
        value={value}
        onChange={(event) => onChange(event.target.value as ThemePreference)}
      >
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}
