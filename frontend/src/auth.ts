import { useSyncExternalStore } from 'react'
import { ApiError, apiRequest, setUnauthorizedHandler } from './api'

export interface AuthUser {
  id: string
  email: string
  username: string
}

export interface Session {
  access_token: string
  /** Erişim token'ının bitiş zamanı (epoch ms). */
  expires_at: number
  user: AuthUser
}

interface TokenResponse {
  access_token: string
  expires_in: number
  user: AuthUser
}

const STORAGE_KEY = 'rota.session'
// Daha önce giriş yapıldı mı? Yalnızca "refresh cookie'si olabilir" ipucu: hiç giriş
// yapmamış misafirler için açılışta boşuna /auth/refresh çağrılmasın. Gizli değer içermez.
const HINT_KEY = 'rota.hint'
// Erişim token'ı bitmeden bu kadar önce sessizce yenilenir.
const REFRESH_MARGIN_MS = 60_000
const RETRY_MS = 30_000
// Sunucu çok kısa ömürlü token dönse bile yenileme döngüsüne girmemek için alt sınır.
const MIN_REFRESH_DELAY_MS = 5_000

// Oturum bellekte tutulur, sayfa yenilenince anında geri gelsin diye localStorage'a da yazılır.
// Burada yalnızca KISA ömürlü (backend: JWT_EXPIRE_MINUTES) erişim token'ı durur; asıl uzun
// ömürlü kimlik refresh token'dır ve httpOnly cookie'dedir, JavaScript onu hiç göremez.
function readStored(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const s = JSON.parse(raw) as Session
    return s.expires_at > Date.now() ? s : null
  } catch {
    return null
  }
}

function hasHint(): boolean {
  try {
    return localStorage.getItem(HINT_KEY) === '1'
  } catch {
    return false
  }
}

let current: Session | null = readStored()
// Açılışta oturum yok ama giriş ipucu var: refresh cookie'siyle sessizce geri kazanmayı deneriz.
// Bu sürede UI "misafir" gibi davranıp yanlış karar vermesin diye ayrı bir bayrak.
let loading = current === null && hasHint()
let timer: ReturnType<typeof setTimeout> | undefined
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((l) => l())
}

function store(next: Session | null) {
  current = next
  try {
    if (next) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      localStorage.setItem(HINT_KEY, '1')
    } else {
      localStorage.removeItem(STORAGE_KEY)
      localStorage.removeItem(HINT_KEY)
    }
  } catch {
    /* depolama kapalı: oturum yalnızca bu sekme açıkken geçerli */
  }
}

function schedule(next: Session | null, delay?: number) {
  clearTimeout(timer)
  if (!next) return
  timer = setTimeout(
    () => void refreshSession(),
    delay ?? Math.max(next.expires_at - Date.now() - REFRESH_MARGIN_MS, MIN_REFRESH_DELAY_MS),
  )
}

function setSession(next: Session | null) {
  store(next)
  schedule(next)
  emit()
}

function fromResponse(r: TokenResponse): Session {
  return { access_token: r.access_token, expires_at: Date.now() + r.expires_in * 1000, user: r.user }
}

async function doRefresh(staleToken: string | undefined): Promise<void> {
  // Başka bir sekme bizden önce yenilediyse (localStorage'da, değiştirmek üzere olduğumuzdan
  // FARKLI ve taze bir token var) onu al, tekrar yenileme: refresh token her kullanımda döner,
  // aynı anda iki sekme yenilerse biri reddedilir.
  const stored = readStored()
  if (stored && stored.access_token !== staleToken && stored.expires_at - Date.now() > REFRESH_MARGIN_MS) {
    current = stored
    return
  }
  current = fromResponse(await apiRequest<TokenResponse>('/auth/refresh', { method: 'POST' }))
  store(current)
}

// Cookie'deki refresh token'la yeni erişim token'ı alır. Yalnızca sunucu token'ı açıkça
// reddederse (401: süre doldu, başka yerden çıkış yapıldı, token çalındı) yerel oturum
// kapanır; ağ/sunucu hatasında oturum korunur ve kısa süre sonra tekrar denenir.
async function refreshSession(): Promise<void> {
  const stale = current?.access_token
  try {
    // Sekmeler arası kilit: Web Locks varsa aynı anda tek sekme yeniler.
    if (navigator.locks) await navigator.locks.request('rota-refresh', () => doRefresh(stale))
    else await doRefresh(stale)
    schedule(current)
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      store(null)
      clearTimeout(timer)
    } else {
      schedule(current, RETRY_MS)
    }
  } finally {
    loading = false
    emit()
  }
}

export function signOut() {
  // Sunucudaki refresh token'ı iptal et ve cookie'yi sildir; yanıtı beklemeden yerel oturumu kapat.
  void apiRequest<void>('/auth/logout', { method: 'POST' }).catch(() => undefined)
  setSession(null)
}

export async function signIn(email: string, password: string) {
  setSession(fromResponse(await apiRequest<TokenResponse>('/auth/login', { method: 'POST', body: { email, password } })))
}

// Kayıt başarılıysa backend doğrudan oturum açar (e-posta onayı yok).
export async function signUp(email: string, username: string, password: string) {
  setSession(
    fromResponse(
      await apiRequest<TokenResponse>('/auth/register', { method: 'POST', body: { email, username, password } }),
    ),
  )
}

export async function updateUsername(username: string) {
  if (!current) return
  const user = await apiRequest<AuthUser>('/me', { method: 'PATCH', body: { username }, token: current.access_token })
  setSession({ ...current, user })
}

export async function changePassword(currentPassword: string, newPassword: string) {
  if (!current) return
  // Backend başka cihazlardaki oturumları kapatır ve bu cihaz için yeni refresh cookie verir.
  await apiRequest<void>('/me/password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
    token: current.access_token,
  })
}

// Hesabı ve tüm verisini kalıcı siler (backend şifreyi doğrular, çerezi de sildirir). Yanlış
// şifrede fırlatır ve oturum açık kalır; başarıda yerel oturum kapanır. Çıkış çağrısı
// (/auth/logout) gerekmez: refresh token'lar sunucuda zaten silindi.
export async function deleteAccount(password: string) {
  if (!current) return
  await apiRequest<void>('/me', { method: 'DELETE', body: { password }, token: current.access_token })
  setSession(null)
}


// Şifre sıfırlama bağlantısı iste. Backend hesap var olsun olmasın aynı cevabı verir
// (hesap var mı bilgisi sızmasın); bu yüzden dönüş değeri yok, başarı = "istek alındı".
export async function requestPasswordReset(email: string) {
  await apiRequest<unknown>('/auth/forgot', { method: 'POST', body: { email } })
}

// E-postadaki token'la yeni şifre belirler. Backend tüm oturumları kapatır ve çerezi
// siler; bu tarayıcıdaki yerel oturum da (varsa) kapatılır, kullanıcı yeni şifreyle girer.
export async function resetPassword(token: string, newPassword: string) {
  await apiRequest<void>('/auth/reset', { method: 'POST', body: { token, new_password: newPassword } })
  setSession(null)
}

// Sunucuda hangi hesap özellikleri açık. Şifre sıfırlama e-posta (SMTP) gerektirir; kapalıysa
// arayüz "şifremi unuttum" bağlantısını GÖSTERMEZ (hiç gelmeyecek bir e-posta vaat etmez).
// Ulaşılamazsa kapalı varsayılır.
export async function fetchAuthCapabilities(): Promise<{ password_reset: boolean }> {
  try {
    return await apiRequest<{ password_reset: boolean }>('/auth/capabilities')
  } catch {
    return { password_reset: false }
  }
}

// Token'la 401 alındı (erişim token'ı beklenenden önce geçersiz oldu): yenilemeyi dene;
// o da reddedilirse refreshSession yerel oturumu kapatır.
setUnauthorizedHandler(() => void refreshSession())

if (typeof window !== 'undefined') {
  if (current) schedule(current)
  else if (loading) void refreshSession()

  // Uyku/arka plan sonrası zamanlayıcılar geç çalışabilir; sekme görününce süreye bak.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && current && current.expires_at - Date.now() < REFRESH_MARGIN_MS) {
      void refreshSession()
    }
  })

  // Başka sekmede giriş/çıkış/yenileme olduysa bu sekme de aynı oturuma geçsin.
  window.addEventListener('storage', (e) => {
    if (e.key !== STORAGE_KEY && e.key !== null) return
    current = readStored()
    schedule(current)
    emit()
  })
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// React dışından (ve testlerden) oturumu okumak için; kancalar da bunları kullanır.
export function getSession(): Session | null {
  return current
}

export function isAuthLoading(): boolean {
  return loading
}

// Giriş isteğe bağlı: oturum yoksa null (misafir).
export function useSession(): Session | null {
  return useSyncExternalStore(subscribe, getSession)
}

// Açılışta refresh cookie'siyle oturum geri kazanılırken true (bu sürede "misafir" kararı verme).
export function useAuthLoading(): boolean {
  return useSyncExternalStore(subscribe, isAuthLoading)
}
