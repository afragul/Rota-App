// Stitch "rota_app_logo" — işaret + wordmark. Wordmark rengi temaya uyar (ink).
export function Logo({ className = 'h-8 w-auto' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 120 40" fill="none" role="img" aria-label="Rota">
      <rect x="2" y="6" width="28" height="28" rx="8" fill="#E8603C" />
      <path
        d="M10 20C10 16 14 13 18 13C22 13 22 19 18 19C14 19 14 27 22 27"
        stroke="#FFFFFF"
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="20" r="2" fill="#FFFFFF" />
      <circle cx="22" cy="27" r="2.2" fill="#FFFFFF" />
      <text
        x="38"
        y="27"
        fontFamily="Inter, sans-serif"
        fontSize="21"
        fontWeight="800"
        fill="rgb(var(--c-ink))"
        letterSpacing="-0.5px"
      >
        rota
      </text>
      <circle cx="92" cy="15" r="3" fill="#E8603C" />
    </svg>
  )
}
