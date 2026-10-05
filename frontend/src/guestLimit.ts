// Hesapsız (misafir) kullanıcılar için ücretsiz plan hakkı. Sayaç yalnızca bu
// tarayıcıda (localStorage) tutulur; yani bir kota değil, kayda yönlendirme amaçlı
// yumuşak bir sınırdır. Gerçek zorlama backend'de JWT doğrulamasıyla yapılmalı.
export const GUEST_PLAN_LIMIT = 3

const STORAGE_KEY = 'rota-guest-plan-count'

export function guestPlanCount(): number {
  try {
    const n = Number(localStorage.getItem(STORAGE_KEY))
    return Number.isFinite(n) && n > 0 ? n : 0
  } catch {
    /* localStorage erişilemezse (gizli sekme vb.) sınırsız say */
    return 0
  }
}

export function guestLimitReached(): boolean {
  return guestPlanCount() >= GUEST_PLAN_LIMIT
}

export function recordGuestPlan(): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(guestPlanCount() + 1))
  } catch {
    /* yazılamazsa sayaç artmaz */
  }
}
