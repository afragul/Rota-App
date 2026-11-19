// Bugünlük logosu (public/logo.png) + wordmark. Wordmark rengi temaya uyar (ink).
export function Logo({ className = 'h-8 w-auto' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`} role="img" aria-label="Bugünlük">
      <img src="/logo.png" alt="" className="h-full w-auto" />
      <span className="font-extrabold text-ink text-[19px] tracking-tight leading-none">Bugünlük</span>
    </span>
  )
}
