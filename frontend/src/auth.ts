import { useSyncExternalStore } from 'react'
import { apiRequest, setUnauthorizedHandler } from './api'

export interface AuthUser {
  id: string
  email: string
  username: string
}

export interface Session {
  access_token: string
  /** Token'ın bitiş zamanı (epoch ms). */
  expires_at: number
  user: AuthUser
}

interface TokenResponse {
  access_token: string
  expires_in: number
  user: AuthUser
}

const STORAGE_KEY = 'rota.session'

// Oturum bellekte tutulur ve sayfa yenilenince geri gelsin diye localStorage'a yazılır.
// Not: token localStorage'da durduğu için XSS'e karşı CSP (vite.config.ts) ve çıktı
// kaçırma önemli; token kısa ömürlü (backend JWT_EXPIRE_MINUTES) ve süresi dolunca atılır.
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

let current: Session | null = readStored()
let expiryTimer: ReturnType<typeof setTimeout> | undefined
const listeners = new Set<() => void>()

function persist(next: Session | null) {
  current = next
  try {
    if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* depolama kapalı: oturum yalnızca bu sekme açıkken geçerli */
  }
  clearTimeout(expiryTimer)
  if (next) expiryTimer = setTimeout(signOut, Math.max(next.expires_at - Date.now(), 0))
  listeners.forEach((l) => l())
}

function fromResponse(r: TokenResponse): Session {
  return { access_token: r.access_token, expires_at: Date.now() + r.expires_in * 1000, user: r.user }
}

export function signOut() {
  persist(null)
}

export async function signIn(email: string, password: string) {
  persist(fromResponse(await apiRequest<TokenResponse>('/auth/login', { method: 'POST', body: { email, password } })))
}

// Kayıt başarılıysa backend doğrudan oturum açar (e-posta onayı yok).
export async function signUp(email: string, username: string, password: string) {
  persist(
    fromResponse(
      await apiRequest<TokenResponse>('/auth/register', { method: 'POST', body: { email, username, password } }),
    ),
  )
}

export async function updateUsername(username: string) {
  if (!current) return
  const user = await apiRequest<AuthUser>('/me', { method: 'PATCH', body: { username }, token: current.access_token })
  persist({ ...current, user })
}

export async function changePassword(currentPassword: string, newPassword: string) {
  if (!current) return
  await apiRequest<void>('/me/password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
    token: current.access_token,
  })
}

setUnauthorizedHandler(signOut)
if (current) persist(current) // süre dolumu zamanlayıcısını kur

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// Giriş isteğe bağlı: oturum yoksa null (misafir). Oturum localStorage'dan senkron
// okunduğu için "yükleniyor" durumu yok.
export function useSession(): Session | null {
  return useSyncExternalStore(subscribe, () => current)
}
