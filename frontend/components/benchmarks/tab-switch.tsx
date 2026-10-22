import { cn } from "cn";

/** A row of underlined tabs that switch what the grid below shows. */
export function TabSwitch<K extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Record<K, string>;
  value: K;
  onChange: (key: K) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex gap-4 border-b border-rule">
      {(Object.keys(options) as K[]).map((key) => (
        <button
          key={key}
          type="button"
          aria-pressed={key === value}
          onClick={() => onChange(key)}
          className={cn(
            "-mb-px border-b-2 py-1 text-sm",
            key === value ? "border-signal text-ink" : "border-transparent text-ink-2",
          )}
        >
          {options[key]}
        </button>
      ))}
    </div>
  );
}
