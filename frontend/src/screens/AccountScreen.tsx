import type { Session } from '../auth'
import { useEffect, useState } from 'react'
import { authErrorText } from '../authErrors'
import {
  changePassword,
  deleteAccount,
  fetchAuthCapabilities,
  requestPasswordReset,
  resetPassword,
  signIn,
  signOut,
  signUp,
  updateUsername,
} from '../auth'
import { Icon } from '../components/Icon'
import { listFavoritePlaces, removeFavoritePlace, type FavoritePlace } from '../favoritePlaces'
import { mapsUrl } from '../meta'
import { deleteSavedPlan, listSavedPlans, shareUrl, type SavedPlanSummary } from '../savedPlans'

interface Props {
  session: Session | null
  onOpenSaved: (id: string) => void
  onOpenPrivacy: () => void
  /** Kullanıcı bilerek çıkış yaptı ya da hesabını sildi (süresi dolan oturum bunu çağırmaz). */
  onLoggedOut: () => void
  /** E-postadaki sıfırlama bağlantısından gelen token (varsa yeni şifre formu açılır). */
  resetToken: string | null
  onResetDone: () => void
}

type Mode = 'login' | 'register' | 'forgot'
type PlanSummary = SavedPlanSummary

// Kısıtlama yok, sadece emoji yasak (Unicode "resimsel" sembol aralığı).
const hasEmoji = (s: string) => /\p{Extended_Pictographic}/u.test(s)
const invalidUsername = (s: string) => s.trim().length === 0 || hasEmoji(s)
const inputClass =
  'w-full h-12 px-4 bg-surface-container-low text-ink font-body-md text-body-md rounded-xl placeholder:text-text-secondary/70 focus:outline-none focus:bg-surface'

function ChangePasswordForm({ onDone }: { onDone: () => void }) {
  const [current, setCurrent] = useState('')
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
    try {
      await changePassword(current, password)
      onDone()
    } catch (err) {
      setError(authErrorText(err))
    } finally {
      setSubmitting(false)
    }
  }

  const field = (id: string, label: string, value: string, set: (v: string) => void, auto: string, min?: number) => (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-label-md text-label-md text-ink font-semibold">
        {label}
      </label>
      <input
        id={id}
        type="password"
        autoComplete={auto}
        required
        minLength={min}
        maxLength={128}
        value={value}
        onChange={(e) => set(e.target.value)}
        className={inputClass}
      />
    </div>
  )

  return (
    <form onSubmit={submit} className="flex flex-col gap-space-md p-space-md">
      <div className="flex flex-col gap-1.5 mb-2">
        <h2 className="font-headline-xl-mobile text-headline-xl-mobile text-ink tracking-tight">Şifre değiştir</h2>
        <p className="font-body-md text-body-md text-text-secondary">Önce mevcut şifreni, sonra yenisini gir.</p>
      </div>
      {field('current-password', 'Mevcut şifre', current, setCurrent, 'current-password')}
      {field('new-password', 'Yeni şifre (en az 8 karakter)', password, setPassword, 'new-password', 8)}
      {field('new-password-confirm', 'Yeni şifre (tekrar)', confirm, setConfirm, 'new-password', 8)}
      {error && (
        <div className="bg-error-container/60 rounded-xl p-space-sm" role="alert">
          <p className="font-body-sm text-body-sm text-on-error-container">{error}</p>
        </div>
      )}
      <div className="flex gap-space-sm">
        <button
          type="button"
          onClick={onDone}
          className="h-12 px-5 rounded-xl bg-surface-container-high text-ink font-label-md text-label-md"
        >
          Vazgeç
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="flex-1 h-12 rounded-xl bg-plan-a text-on-primary font-label-md text-label-md disabled:opacity-50"
        >
          {submitting ? 'Kaydediliyor...' : 'Şifreyi güncelle'}
        </button>
      </div>
    </form>
  )
}

// E-postadaki bağlantıyla gelen kullanıcı: yeni şifreyi belirler. Token tek kullanımlık ve
// süreli; geçersizse backend'in mesajı gösterilir ve yeni bağlantı istemesi söylenir.
function ResetPasswordForm({ token, onDone, onCancel }: { token: string; onDone: () => void; onCancel: () => void }) {
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
    try {
      await resetPassword(token, password)
      onDone()
    } catch (err) {
      setError(authErrorText(err))
      setSubmitting(false)
    }
  }

  const field = (id: string, label: string, value: string, set: (v: string) => void) => (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-label-md text-label-md text-ink font-semibold">
        {label}
      </label>
      <input
        id={id}
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        maxLength={128}
        value={value}
        onChange={(e) => set(e.target.value)}
        className={inputClass}
      />
    </div>
  )

  return (
    <form onSubmit={submit} className="flex flex-col gap-space-md pt-space-lg">
      <div className="flex flex-col gap-1.5 mb-2">
        <h2 className="font-headline-xl-mobile text-headline-xl-mobile text-ink tracking-tight">Yeni şifre belirle</h2>
        <p className="font-body-md text-body-md text-text-secondary">
          Hesabın için yeni bir şifre seç. Şifren değişince diğer cihazlardaki oturumların kapanır.
        </p>
      </div>
      {field('reset-password', 'Yeni şifre (en az 8 karakter)', password, setPassword)}
      {field('reset-password-confirm', 'Yeni şifre (tekrar)', confirm, setConfirm)}
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
      <button type="button" onClick={onCancel} className="font-label-md text-label-md text-primary">
        Vazgeç
      </button>
    </form>
  )
}

// Geri alınamaz bir işlem: ne silineceği açıkça söylenir ve şifre istenir (çalınmış bir
// oturum tek başına hesabı yok edemesin). Başarılıysa oturum kapanır, AccountScreen giriş
// formuna döner ve `onDone` bilgi mesajını gösterir.
function DeleteAccountForm({ onCancel, onDone }: { onCancel: () => void; onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await deleteAccount(password)
      onDone()
    } catch (err) {
      setError(authErrorText(err))
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="bg-error-container/40 rounded-xl p-space-md flex flex-col gap-space-sm">
      <h3 className="font-label-lg text-label-lg text-error font-bold">Hesabı kalıcı olarak sil</h3>
      <p className="font-body-sm text-body-sm text-ink">
        Hesabın, kayıtlı rotaların, favori mekanların ve ziyaret geçmişin silinir. Paylaştığın rota linkleri de
        çalışmaz. <strong>Bu işlem geri alınamaz.</strong>
      </p>
      <label htmlFor="delete-password" className="font-label-md text-label-md text-ink font-semibold">
        Onaylamak için şifreni gir
      </label>
      <input
        id="delete-password"
        type="password"
        autoComplete="current-password"
        required
        maxLength={128}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className={inputClass}
      />
      {error && (
        <p className="font-body-sm text-body-sm text-error" role="alert">
          {error}
        </p>
      )}
      <div className="flex gap-space-sm">
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          className="h-12 px-5 rounded-xl bg-surface-container-high text-ink font-label-md text-label-md disabled:opacity-50"
        >
          Vazgeç
        </button>
        <button
          type="submit"
          disabled={submitting || password.length === 0}
          className="flex-1 h-12 rounded-xl bg-error text-on-primary font-label-md text-label-md disabled:opacity-50"
        >
          {submitting ? 'Siliniyor...' : 'Hesabımı sil'}
        </button>
      </div>
    </form>
  )
}

function LoggedInPanel({
  session,
  onOpenSaved,
  onAccountDeleted,
  onSignedOut,
}: {
  session: Session
  onOpenSaved: (id: string) => void
  onAccountDeleted: () => void
  onSignedOut: () => void
}) {
  const [deletingAccount, setDeletingAccount] = useState(false)
  const username = session.user.username
  const [newUsername, setNewUsername] = useState(username)
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [savingUsername, setSavingUsername] = useState(false)
  const [editingUsername, setEditingUsername] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  const [plans, setPlans] = useState<PlanSummary[] | 'loading'>('loading')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [favoritePlaces, setFavoritePlaces] = useState<FavoritePlace[] | 'loading'>('loading')

  const loadPlans = () => {
    listSavedPlans(session.access_token).then(({ data }) => setPlans(data ?? []))
  }

  const loadFavoritePlaces = () => {
    listFavoritePlaces(session.access_token).then(({ data }) => setFavoritePlaces(data ?? []))
  }

  useEffect(() => {
    loadPlans()
    loadFavoritePlaces()
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
    try {
      await updateUsername(trimmed)
      setEditingUsername(false)
    } catch (err) {
      setUsernameError(authErrorText(err))
    } finally {
      setSavingUsername(false)
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
    await deleteSavedPlan(id, session.access_token)
    loadPlans()
  }

  const removeFavoritePlaceRow = async (placeId: string) => {
    await removeFavoritePlace(placeId, session.access_token)
    loadFavoritePlaces()
  }

  return (
    <div className="flex flex-col gap-space-md pt-space-lg">
      <div className="bg-surface rounded-2xl p-5 shadow-sm flex items-center gap-3.5">
        <div className="w-12 h-12 rounded-2xl bg-primary-fixed/50 flex items-center justify-center flex-shrink-0">
          <Icon name="account_circle" fill className="text-primary text-[28px]" />
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <span className="font-label-lg text-label-lg text-ink font-semibold truncate">
            {username}
          </span>
          <span className="font-body-sm text-body-sm text-text-secondary truncate">{session.user.email}</span>
        </div>
        {!editingUsername && (
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
            Kullanıcı adını değiştir
          </label>
          <input
            id="backfill-username"
            value={newUsername}
            maxLength={50}
            onChange={(e) => setNewUsername(e.target.value)}
            placeholder="örn. beyza_34"
            className={inputClass}
          />
          {usernameError && <p className="font-body-sm text-body-sm text-error">{usernameError}</p>}
          <div className="flex gap-space-sm">
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
          <ChangePasswordForm onDone={() => setChangingPassword(false)} />
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

      <div className="flex flex-col gap-space-sm">
        <h3 className="font-label-lg text-label-lg text-ink font-semibold">Favori Mekanlarım</h3>
        {favoritePlaces === 'loading' && <p className="font-body-sm text-body-sm text-text-secondary">Yükleniyor...</p>}
        {favoritePlaces !== 'loading' && favoritePlaces.length === 0 && (
          <p className="font-body-sm text-body-sm text-text-secondary">
            Henüz favorilediğin bir mekan yok — bir plan detayındaki duraklarda kalp ikonuyla favorileyebilirsin.
          </p>
        )}
        {favoritePlaces !== 'loading' &&
          favoritePlaces.map((p) => (
            <div
              key={p.id}
              role="button"
              tabIndex={0}
              onClick={() => window.open(mapsUrl(p), '_blank', 'noopener,noreferrer')}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') window.open(mapsUrl(p), '_blank', 'noopener,noreferrer')
              }}
              className="bg-surface rounded-xl p-space-md shadow-sm flex items-center gap-space-sm text-left hover:bg-surface-container-low transition-colors cursor-pointer"
            >
              <div className="flex flex-col min-w-0 flex-1">
                <span className="font-label-md text-label-md text-ink font-semibold truncate">{p.name}</span>
                {p.address && <span className="font-body-sm text-body-sm text-text-secondary truncate">{p.address}</span>}
              </div>
              <Icon name="open_in_new" className="text-text-secondary text-[18px] flex-shrink-0" />
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  removeFavoritePlaceRow(p.place_id)
                }}
                aria-label="Favorilerden çıkar"
                className="w-9 h-9 rounded-full flex items-center justify-center text-error flex-shrink-0"
              >
                <Icon name="delete" className="text-[18px]" />
              </button>
            </div>
          ))}
      </div>

      <button
        onClick={() => {
          signOut()
          onSignedOut()
        }}
        className="h-12 rounded-xl bg-surface-container-high text-ink font-label-md text-label-md flex items-center justify-center gap-1.5"
      >
        <Icon name="logout" className="text-[18px]" />
        Çıkış yap
      </button>

      {deletingAccount ? (
        <DeleteAccountForm onCancel={() => setDeletingAccount(false)} onDone={onAccountDeleted} />
      ) : (
        <button
          type="button"
          onClick={() => setDeletingAccount(true)}
          className="h-10 font-label-md text-label-md text-error flex items-center justify-center gap-1.5"
        >
          <Icon name="delete_forever" className="text-[18px]" />
          Hesabımı sil
        </button>
      )}
    </div>
  )
}

// Giriş opsiyonel: uygulama misafir olarak da kullanılabilir, bu ekran sadece
// hesap oluşturup giriş yapmak isteyenler için (bkz. Shell'deki hesap ikonu).
export function AccountScreen({ session, onOpenSaved, onOpenPrivacy, onLoggedOut, resetToken, onResetDone }: Props) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  // Sunucuda SMTP yoksa "şifremi unuttum" gösterilmez (bkz. auth.ts::fetchAuthCapabilities).
  const [canReset, setCanReset] = useState(false)

  useEffect(() => {
    let alive = true
    void fetchAuthCapabilities().then((c) => alive && setCanReset(c.password_reset))
    return () => {
      alive = false
    }
  }, [])

  // Sıfırlama bağlantısı oturumdan önce gelir: giriş yapmış olsa bile yeni şifre sorulur.
  if (resetToken) {
    return (
      <ResetPasswordForm
        token={resetToken}
        onCancel={onResetDone}
        onDone={() => {
          onResetDone()
          setMode('login')
          setNotice('Şifren güncellendi. Yeni şifrenle giriş yapabilirsin.')
        }}
      />
    )
  }

  if (session) {
    return (
      <LoggedInPanel
        session={session}
        onOpenSaved={onOpenSaved}
        // Hesap silinince oturum kapanır ve bu bileşen giriş formuna döner; kullanıcı ne olduğunu görsün.
        onAccountDeleted={() => {
          onLoggedOut()
          setNotice('Hesabın ve tüm verilerin kalıcı olarak silindi.')
        }}
        onSignedOut={onLoggedOut}
      />
    )
  }

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

    try {
      if (mode === 'forgot') {
        // Cevap hesap var olsun olmasın aynı: "kayıtlıysa gönderdik" demekten fazlasını bilmiyoruz.
        await requestPasswordReset(email)
        setNotice('Bu e-posta kayıtlıysa şifre sıfırlama bağlantısı gönderdik. Gelen kutunu ve spam klasörünü kontrol et.')
      } else if (mode === 'register') {
        const normalized = username.trim()
        if (invalidUsername(normalized)) {
          setError('Kullanıcı adı boş olamaz ve emoji içeremez')
          return
        }
        // Kayıt başarılıysa backend doğrudan oturum açar; ekran LoggedInPanel'e geçer.
        await signUp(email, normalized, password)
      } else {
        await signIn(email, password)
      }
    } catch (err) {
      setError(authErrorText(err))
    } finally {
      setSubmitting(false)
    }
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
            minLength={2}
            maxLength={50}
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
          maxLength={254}
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
            minLength={mode === 'register' ? 8 : 1}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
          {mode === 'register' && (
            <p className="font-body-sm text-body-sm text-text-secondary">En az 8 karakter.</p>
          )}
          {mode === 'login' && canReset && (
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

      <p className="font-body-sm text-body-sm text-text-secondary text-center">
        {mode === 'register' ? 'Kayıt olarak ' : ''}
        <button type="button" onClick={onOpenPrivacy} className="text-primary underline">
          Gizlilik ve Aydınlatma Metni
        </button>
        {mode === 'register' ? "'ni okuduğunu onaylarsın." : "'ne göz atabilirsin."}
      </p>

      <button
        type="button"
        onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
        className="font-label-md text-label-md text-primary"
      >
        {mode === 'login' ? 'Hesabın yok mu? Kayıt ol' : mode === 'register' ? 'Zaten hesabın var mı? Giriş yap' : 'Giriş ekranına dön'}
      </button>
    </form>
  )
}
