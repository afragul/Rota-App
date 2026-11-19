// Bugünlük logosu (public/logo.png). Yalnızca işaret; marka adı Shell'de başlığın üstünde durur.
export function Logo({ className = 'h-9 w-auto' }: { className?: string }) {
  return <img src="/logo.png" alt="Bugünlük" className={className} />
}
