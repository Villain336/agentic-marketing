"use client";

export function ToggleRow({ label, description, checked, onChange }: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <div className="text-sm font-medium text-surface-700">{label}</div>
        <div className="text-xs text-surface-400">{description}</div>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`w-10 h-5 rounded-full flex items-center transition-all flex-shrink-0 ${
          checked ? "bg-brand-500 justify-end" : "bg-surface-300 justify-start"
        }`}
        role="switch"
        aria-checked={checked}
        aria-label={label}
      >
        <div className="w-4 h-4 rounded-full bg-white shadow-sm mx-0.5" />
      </button>
    </div>
  );
}
