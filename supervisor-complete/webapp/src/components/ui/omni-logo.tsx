export function OmniLogo({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Globe */}
      <circle cx="32" cy="32" r="14" stroke="currentColor" strokeWidth="2" fill="none" />
      <ellipse cx="32" cy="32" rx="8" ry="14" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <line x1="18" y1="32" x2="46" y2="32" stroke="currentColor" strokeWidth="1.5" />
      <ellipse cx="32" cy="26" rx="12" ry="4" stroke="currentColor" strokeWidth="1" fill="none" />
      <ellipse cx="32" cy="38" rx="12" ry="4" stroke="currentColor" strokeWidth="1" fill="none" />

      {/* Agent nodes orbiting the globe */}
      <circle cx="32" cy="6" r="4" fill="currentColor" opacity="0.9" />
      <circle cx="52" cy="12" r="3.5" fill="currentColor" opacity="0.8" />
      <circle cx="58" cy="32" r="4" fill="currentColor" opacity="0.9" />
      <circle cx="52" cy="52" r="3.5" fill="currentColor" opacity="0.8" />
      <circle cx="32" cy="58" r="4" fill="currentColor" opacity="0.9" />
      <circle cx="12" cy="52" r="3.5" fill="currentColor" opacity="0.8" />
      <circle cx="6" cy="32" r="4" fill="currentColor" opacity="0.9" />
      <circle cx="12" cy="12" r="3.5" fill="currentColor" opacity="0.8" />

      {/* Connection lines from globe to agents */}
      <line x1="32" y1="18" x2="32" y2="10" stroke="currentColor" strokeWidth="1" opacity="0.4" />
      <line x1="42" y1="22" x2="49" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
      <line x1="46" y1="32" x2="54" y2="32" stroke="currentColor" strokeWidth="1" opacity="0.4" />
      <line x1="42" y1="42" x2="49" y2="49" stroke="currentColor" strokeWidth="1" opacity="0.4" />
      <line x1="32" y1="46" x2="32" y2="54" stroke="currentColor" strokeWidth="1" opacity="0.4" />
      <line x1="22" y1="42" x2="15" y2="49" stroke="currentColor" strokeWidth="1" opacity="0.4" />
      <line x1="18" y1="32" x2="10" y2="32" stroke="currentColor" strokeWidth="1" opacity="0.4" />
      <line x1="22" y1="22" x2="15" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
    </svg>
  );
}
