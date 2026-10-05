import type { Session } from '@supabase/supabase-js'
import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import { deleteSavedPlan, listSavedPlans, shareUrl, type SavedPlan } from '../savedPlans'
import { supabase } from '../supabase'

// Supabase Auth hata mesajları İngilizce geliyor; bilinenleri Türkçeye çevirir.
function authErrorText(message: string): string {
  const m = message.toLowerCase()
  if (m.includes('invalid login credentials')) return 'E-posta veya şifre hatalı.'
  if (m.includes('email not confirmed')) return 'E-posta adresin henüz onaylanmamış. Gelen kutunu kontrol et.'
  if (m.includes('user already registered')) return 'Bu e-posta ile zaten bir hesap var.'
  if (m.includes('password should be at least')) return 'Şifre en az 6 karakter olmalı.'
  if (m.includes('same password')) return 'Yeni şifre eskisinden farklı olmalı.'
  if (m.includes('rate limit') || m.includes('too many')) return 'Çok fazla deneme yapıldı, biraz sonra tekrar dene.'
  if (m.includes('invalid email') || m.includes('unable to validate email')) return 'Geçerli bir e-posta adresi gir.'
  if (m.includes('failed to fetch') || m.includes('network')) return 'Bağlantı hatası, internetini kontrol et.'
  return 'Bir hata oluştu, tekrar dene.'
}

interface Props {
  session: Session | null
  /** Kullanıcı şifre sıfırlama e-postasındaki linke tıklayıp geri döndüğünde true. */
  recovery: boolean
  onRecoveryDone: () => void
  onOpenSaved: (id: string) => void
}

type Mode = 'login' | 'register' | 'forgot'
type PlanSummary = Pick<SavedPlan, 'id' | 'theme' | 'title' | 'summary' | 'created_at'>

// Kısıtlama yok, sadece emoji yasak (Unicode "resimsel" sembol aralığı).
const hasEmoji = (s: string) => /\p{Extended_Pictographic}/u.test(s)
const invalidUsername = (s: string) => s.trim().length === 0 || hasEmoji(s)
const inputClass =
  'w-full h-12 px-4 bg-surface-container-low text-ink font-body-md text-body-md rounded-xl placeholder:text-text-secondary/70 focus:outline-none focus:bg-surface'

function NewPasswordForm({ onDone }: { onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirm) {
      setError('Şifreler eşleşmiyor')
      return
    }
    setSubmitting(true)
    setError(null)
    const { error } = await supabase.auth.updateUser({ password })
    setSubmitting(false)
    if (error) setError(authErrorText(error.message))
    else onDone()
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-space-md pt-space-lg">
      <div className="flex flex-col gap-1.5 mb-2">
        <h2 className="font-headline-xl-mobile text-headline-xl-mobile text-ink tracking-tight">Yeni şifre belirle</h2>
        <p className="font-body-md text-body-md text-text-secondary">Hesabın için yeni bir şifre seç.</p>
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="new-password" className="font-label-md text-label-md text-ink font-semibold">
          Yeni şifre
        </label>
        <input
          id="new-password"
          type="password"
          autoComplete="new-password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputClass}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="new-password-confirm" className="font-label-md text-label-md text-ink font-semibold">
          Yeni şifre (tekrar)
        </label>
        <input
          id="new-password-confirm"
          type="password"
          autoComplete="new-password"
          required
          minLength={6}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className={inputClass}
        />
      </div>
      {error && (
        <div className="bg-error-container/60 rounded-xl p-space-sm" role="alert">
          <p className="font-body-sm text-body-sm text-on-error-container">{error}</p>
        </div>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="h-12 rounded-xl bg-plan-a text-on-primary font-label-md text-label-md disabled:opacity-50"
      >
        {submitting ? 'Kaydediliyor...' : 'Şifreyi güncelle'}
      </button>
    </form>
  )
}

function LoggedInPanel({ session, onOpenSaved }: { session: Session; onOpenSaved: (id: string) => void }) {
  const [username, setUsername] = useState<string | null | 'loading'>('loading')
  const [newUsername, setNewUsername] = useState('')
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [savingUsername, setSavingUsername] = useState(false)
  const [editingUsername, setEditingUsername] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  const [plans, setPlans] = useState<PlanSummary[] | 'loading'>('loading')
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const loadPlans = () => {
    listSavedPlans(session.user.id).then(({ data }) => setPlans(data ?? []))
  }

  useEffect(() => {
    supabase
      .from('profiles')
      .select('username')
      .eq('id', session.user.id)
      .maybeSingle()
      .then(({ data }) => {
        const current = data?.username ?? null
        setUsername(current)
        setNewUsername(current ?? '')
        if (current === null) setEditingUsername(true)
      })
    loadPlans()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.user.id])

  const saveUsername = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = newUsername.trim()
    if (invalidUsername(trimmed)) {
      setUsernameError('Emoji kullanılamaz')
      return
    }
    setSavingUsername(true)
    setUsernameError(null)
    const { error } = await supabase.from('profiles').upsert({ id: session.user.id, username: trimmed })
    setSavingUsername(false)
    if (error) setUsernameError(error.message.includes('duplicate') ? 'Bu kullanıcı adı alınmış' : error.message)
    else {
      setUsername(trimmed)
      setEditingUsername(false)
    }
  }

  const copyLink = async (id: string) => {
    try {
      await navigator.clipboard.writeText(shareUrl(id))
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      /* pano erişilemedi */
    }
  }

  const removePlan = async (id: string) => {
    await deleteSavedPlan(id)
    loadPlans()
  }

  return (
    <div className="flex flex-col gap-space-md pt-space-lg">
      <div className="bg-surface rounded-2xl p-5 shadow-sm flex items-center gap-3.5">
        <div className="w-12 h-12 rounded-2xl bg-primary-fixed/50 flex items-center justify-center flex-shrink-0">
          <Icon name="account_circle" fill className="text-primary text-[28px]" />
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <span className="font-label-lg text-label-lg text-ink font-semibold truncate">
            {username === 'loading' ? '...' : (username ?? session.user.email)}
          </span>
          <span className="font-body-sm text-body-sm text-text-secondary truncate">{session.user.email}</span>
        </div>
        {username !== 'loading' && !editingUsername && (
          <button
            type="button"
            onClick={() => setEditingUsername(true)}
            aria-label="Kullanıcı adını düzenle"
            className="w-9 h-9 rounded-full flex items-center justify-center text-ink hover:text-primary flex-shrink-0"
          >
            <Icon name="edit" className="text-[18px]" />
          </button>
        )}
      </div>

      {editingUsername && (
        <form onSubmit={saveUsername} className="bg-surface rounded-xl p-space-md shadow-sm flex flex-col gap-space-sm">
          <label htmlFor="backfill-username" className="font-label-md text-label-md text-ink font-semibold">
            {username === null ? 'Kullanıcı adı belirle' : 'Kullanıcı adını değiştir'}
          </label>
          <input
            id="backfill-username"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            placeholder="örn. beyza_34"
            className={inputClass}
          />
          {usernameError && <p className="font-body-sm text-body-sm text-error">{usernameError}</p>}
          <div className="flex gap-space-sm">
            {username !== null && (
              <button
                type="button"
                onClick={() => {
                  setEditingUsername(false)
                  setNewUsername(username)
                  setUsernameError(null)
                }}
                className="h-11 px-5 rounded-xl bg-surface-container-high text-ink font-label-md text-label-md"
              >
                Vazgeç
              </button>
            )}
            <button
              type="submit"
              disabled={savingUsername}
              className="flex-1 h-11 rounded-xl bg-plan-a text-on-primary font-label-md text-label-md disabled:opacity-50"
            >
              {savingUsername ? 'Kaydediliyor...' : 'Kaydet'}
            </button>
          </div>
        </form>
      )}

      {changingPassword ? (
        <div className="bg-surface rounded-xl shadow-sm">
          <NewPasswordForm onDone={() => setChangingPassword(false)} />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setChangingPassword(true)}
          className="h-12 rounded-xl bg-surface-container-high text-ink font-label-md text-label-md flex items-center justify-center gap-1.5"
        >
          <Icon name="lock_reset" className="text-[18px]" />
          Şifre değiştir
        </button>
      )}

      <div className="flex flex-col gap-space-sm">
        <h3 className="font-label-lg text-label-lg text-ink font-semibold">Kaydedilen Rotalarım</h3>
        {plans === 'loading' && <p className="font-body-sm text-body-sm text-text-secondary">Yükleniyor...</p>}
        {plans !== 'loading' && plans.length === 0 && (
          <p className="font-body-sm text-body-sm text-text-secondary">
            Henüz kaydedilen rotan yok — bir plan detayındaki yıldız ikonuyla kaydedebilirsin.
          </p>
        )}
        {plans !== 'loading' &&
          plans.map((p) => (
            <div
              key={p.id}
              role="button"
              tabIndex={0}
              onClick={() => onOpenSaved(p.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') onOpenSaved(p.id)
              }}
              className="bg-surface rounded-xl p-space-md shadow-sm flex items-center gap-space-sm text-left hover:bg-surface-container-low transition-colors cursor-pointer"
            >
              <div className="flex flex-col min-w-0 flex-1">
                <span className="font-label-md text-label-md text-ink font-semibold truncate">{p.title}</span>
                <span className="font-body-sm text-body-sm text-text-secondary truncate">{p.theme}</span>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  copyLink(p.id)
                }}
                aria-label="Linki kopyala"
                className="w-9 h-9 rounded-full flex items-center justify-center text-ink hover:text-primary flex-shrink-0"
              >
                <Icon name={copiedId === p.id ? 'check' : 'link'} className="text-[18px]" />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  removePlan(p.id)
                }}
                aria-label="Sil"
                className="w-9 h-9 rounded-full flex items-center justify-center text-error flex-shrink-0"
              >
                <Icon name="delete" className="text-[18px]" />
              </button>
            </div>
          ))}
      </div>

      <button
        onClick={() => supabase.auth.signOut()}
        className="h-12 rounded-xl bg-surface-container-high text-ink font-label-md text-label-md flex items-center justify-center gap-1.5"
      >
        <Icon name="logout" className="text-[18px]" />
        Çıkış yap
      </button>
    </div>
  )
}

// Giriş opsiyonel: uygulama misafir olarak da kullanılabilir, bu ekran sadece
// hesap oluşturup giriş yapmak isteyenler için (bkz. Shell'deki hesap ikonu).
export function AccountScreen({ session, recovery, onRecoveryDone, onOpenSaved }: Props) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  // Şifre sıfırlama linkiyle gelindiyse, oturum olsa da önce yeni şifre sorulur.
  if (recovery) return <NewPasswordForm onDone={onRecoveryDone} />

  if (session) return <LoggedInPanel session={session} onOpenSaved={onOpenSaved} />

  const switchMode = (next: Mode) => {
    setMode(next)
    setError(null)
    setNotice(null)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setNotice(null)

    if (mode === 'forgot') {
      const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: window.location.origin })
      setSubmitting(false)
      if (error) setError(authErrorText(error.message))
      else setNotice('Şifre sıfırlama bağlantısı e-postana gönderildi.')
      return
    }

    if (mode === 'register') {
      const normalized = username.trim()
      if (invalidUsername(normalized)) {
        setSubmitting(false)
        setError('Kullanıcı adı boş olamaz ve emoji içeremez')
        return
      }
      const { data: existing } = await supabase.from('profiles').select('id').eq('username', normalized).maybeSingle()
      if (existing) {
        setSubmitting(false)
        setError('Bu kullanıcı adı alınmış')
        return
      }
      const { error } = await supabase.auth.signUp({ email, password, options: { data: { username: normalized } } })
      setSubmitting(false)
      if (error) setError(authErrorText(error.message))
      else setNotice('Kayıt başarılı. E-postana gelen bağlantıyla hesabını onayladıktan sonra giriş yapabilirsin.')
      return
    }

    const { error } = await supabase.auth.signInWithPassword({ email, password })
    setSubmitting(false)
    if (error) setError(authErrorText(error.message))
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-space-md pt-space-lg">
      <div className="flex flex-col gap-1.5 mb-2">
        <h2 className="font-headline-xl-mobile text-headline-xl-mobile text-ink tracking-tight">
          {mode === 'login' ? 'Giriş Yap' : mode === 'register' ? 'Hesap Oluştur' : 'Şifremi Unuttum'}
        </h2>
        <p className="font-body-md text-body-md text-text-secondary">
          {mode === 'forgot'
            ? 'E-posta adresini gir, sana şifre sıfırlama bağlantısı gönderelim.'
            : 'Giriş yapmak zorunlu değil, uygulamayı misafir olarak da kullanabilirsin.'}
        </p>
      </div>

      {mode === 'register' && (
        <div className="flex flex-col gap-1.5">
          <label htmlFor="account-username" className="font-label-md text-label-md text-ink font-semibold">
            Kullanıcı adı
          </label>
          <input
            id="account-username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="örn. beyza_34"
            className={inputClass}
          />
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label htmlFor="account-email" className="font-label-md text-label-md text-ink font-semibold">
          E-posta
        </label>
        <input
          id="account-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputClass}
        />
      </div>

      {mode !== 'forgot' && (
        <div className="flex flex-col gap-1.5">
          <label htmlFor="account-password" className="font-label-md text-label-md text-ink font-semibold">
            Şifre
          </label>
          <input
            id="account-password"
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
          {mode === 'login' && (
            <button type="button" onClick={() => switchMode('forgot')} className="self-end font-label-sm text-label-sm text-primary">
              Şifremi unuttum
            </button>
          )}
        </div>
      )}

      {notice && (
        <div className="bg-success/15 rounded-xl p-space-md" role="status">
          <p className="font-body-md text-body-md text-ink">{notice}</p>
        </div>
      )}
      {error && (
        <div className="bg-error-container/60 rounded-xl p-space-sm" role="alert">
          <p className="font-body-sm text-body-sm text-on-error-container">{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="h-12 rounded-xl bg-plan-a text-on-primary font-label-md text-label-md disabled:opacity-50"
      >
        {submitting ? 'Gönderiliyor...' : mode === 'login' ? 'Giriş Yap' : mode === 'register' ? 'Kayıt Ol' : 'Bağlantı gönder'}
      </button>

      <button
        type="button"
        onClick={() => switchMode(mode === 'register' ? 'login' : mode === 'forgot' ? 'login' : 'register')}
        className="font-label-md text-label-md text-primary"
      >
        {mode === 'login' ? 'Hesabın yok mu? Kayıt ol' : mode === 'register' ? 'Zaten hesabın var mı? Giriş yap' : 'Giriş ekranına dön'}
      </button>
    </form>
  )
}
