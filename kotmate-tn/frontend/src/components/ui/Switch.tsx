// Hand-rolled sliding-pill toggle — no @radix-ui/* dependency in this project yet
// despite shadcn/ui being nominally listed in the tech stack (CLAUDE.md), so this is a
// small standalone component rather than pulling in a whole primitives package for one
// control. Used by every toggle in Settings > Preferences instead of a bare
// `<input type="checkbox">`.
interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
  description?: string;
}

export function Switch({ checked, onChange, disabled, label, description }: SwitchProps) {
  function toggle() {
    if (!disabled) onChange(!checked);
  }

  return (
    <div
      role="switch"
      aria-checked={checked}
      aria-disabled={disabled || undefined}
      tabIndex={disabled ? -1 : 0}
      onClick={toggle}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === " " || e.key === "Enter") {
          e.preventDefault();
          toggle();
        }
      }}
      className={`flex items-center justify-between gap-4 rounded-md py-1 outline-none focus-visible:ring-2 focus-visible:ring-accent ${
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
      }`}
    >
      <span className="flex flex-col gap-0.5 pr-2">
        <span className="text-sm font-medium text-foreground">{label}</span>
        {description && <span className="text-xs text-foreground/50">{description}</span>}
      </span>
      <span
        aria-hidden="true"
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
          checked ? "bg-accent" : "bg-foreground/20"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-background shadow transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </span>
    </div>
  );
}
