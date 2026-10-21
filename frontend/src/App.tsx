import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, createPlan, type LatLng } from './api'
import { useAuthLoading, useSession } from './auth'
import { ErrorBanner } from './components/ErrorBanner'
import { Shell, type NavKey } from './components/Shell'
import { guestLimitReached, recordGuestPlan } from './guestLimit'
import { DEFAULT_PREFS, hasLocation, toRequest, type Preferences } from './prefs'
import { AccountScreen } from './screens/AccountScreen'
import { ClarifyScreen } from './screens/ClarifyScreen'
import { DetailScreen, type UserLocation } from './screens/DetailScreen'
import { NavigationScreen } from './screens/NavigationScreen'
import { LimitScreen } from './screens/LimitScreen'
import { LoadingScreen } from './screens/LoadingScreen'
import { LocationScreen } from './screens/LocationScreen'
import { PreferencesScreen } from './screens/PreferencesScreen'
import { ResultsScreen } from './screens/ResultsScreen'
import { SharedPlanScreen } from './screens/SharedPlanScreen'
import { buildSegments } from './nav'
import { useTheme } from './theme'
import { isClarification, type ApproachRoute, type DayPlan } from './types'

type View =
  | { name: 'location' }
  | { name: 'prefs' }
  | { name: 'loading' }
  | { name: 'limit' }
  | { name: 'clarify'; question: string }
  | { name: 'error'; error: ApiError }
  | { name: 'results' }
  | { name: 'detail'; index: number }
  | { name: 'navigate'; index: number; approach: ApproachRoute }
  | { name: 'account'; from: View }

function errorCopy(error: ApiError): { title: string; message: string } {
  if (error.status === 0) return { title: 'Sunucuya ulaşılamadı', message: 'Bağlantınızı kontrol edip tekrar deneyin.' }
  if (error.message.includes('mekan'))
    return { title: 'Bu bölgede uygun mekân bulunamadı', message: 'Konumu ya da aktivite türlerini değiştirmeyi deneyin.' }
  if (error.status === 422) return { title: 'Girdiler geçersiz', message: 'Konum ve tercihlerinizi kontrol edin.' }
  return { title: 'Plan oluşturulamadı', message: error.message }
}

const TITLES: Record<View['name'], string> = {
  location: 'Rota Oluştur',
  prefs: 'Rota Oluştur',
  loading: 'Günlük Planlar',
  limit: 'Rota Oluştur',
  clarify: 'Rota Oluştur',
  error: 'Günlük Planlar',
  results: 'Günlük Planlar',
  detail: 'Plan Detayı',
  navigate: 'Navigasyon',
  account: 'Hesabım',
}

const NAV_FOR: Record<View['name'], NavKey | null> = {
  location: 'discover',
  prefs: 'preferences',
  clarify: 'preferences',
  loading: 'plans',
  limit: 'preferences',
  error: 'plans',
  results: 'plans',
  detail: 'plans',
  navigate: 'plans',
  account: null,
}

// Şifre sıfırlama e-postasındaki bağlantı `/#reset=<token>` biçimindedir: token fragment'te
// olduğu için sunucuya ve Referer başlığına gitmez. Okuma saf kalır (StrictMode state
// başlatıcılarını iki kez çalıştırır); adres çubuğundan silme App içindeki effect'te yapılır.
function readResetToken(): string | null {
  const match = /^#reset=(.+)$/.exec(window.location.hash)
  return match ? decodeURIComponent(match[1]) : null
}

export default function App() {
  // Tercihler ve son plan ekranlar arasında korunur.
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS)
  const [plan, setPlan] = useState<DayPlan | null>(null)
  // Sıfırlama bağlantısıyla gelindiyse doğrudan hesap ekranında başla (yeni şifre formu orada).
  const [view, setView] = useState<View>(() =>
    readResetToken() ? { name: 'account', from: { name: 'location' } } : { name: 'location' },
  )
  const [userLoc, setUserLoc] = useState<UserLocation>({ status: 'idle' })
  const abort = useRef<AbortController | null>(null)
  const [theme, toggleTheme] = useTheme()
  const session = useSession()
  const authLoading = useAuthLoading()
  const [sharedId, setSharedId] = useState(() => new URLSearchParams(window.location.search).get('shared'))
  const [resetToken, setResetToken] = useState<string | null>(readResetToken)
  // Kaydedilenler listesinden bir rota görüntülenip (silinip) dönüldüğünde Hesabım'ı yeniden yükletir.
  const [accountKey, setAccountKey] = useState(0)

  // Token artık state'te; adres çubuğundan/geçmişten sil (ekran görüntüsü, geçmiş, paylaşım).
  useEffect(() => {
    if (resetToken) window.history.replaceState(null, '', window.location.pathname + window.location.search)
  }, [resetToken])

  // Kullanıcının konumu yalnızca plan detayında, ilk durağa rota için istenir.
  const requestLocation = useCallback(() => {
    if (!navigator.geolocation) return setUserLoc({ status: 'denied' })
    setUserLoc({ status: 'loading' })
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords: LatLng = { latitude: pos.coords.latitude, longitude: pos.coords.longitude }
        setUserLoc({ status: 'ready', coords })
      },
      () => setUserLoc({ status: 'denied' }),
      { timeout: 10000 },
    )
  }, [])

  const submit = useCallback(
    async (clarification?: { question: string; answer: string }) => {
      const base = toRequest(prefs)
      if (!base) return
      // Misafir hakkı dolduysa istek hiç atılmaz; oturum henüz geri kazanılıyorsa engellenmez.
      if (!authLoading && !session && guestLimitReached()) return setView({ name: 'limit' })
      // Backend stateless: soru ve cevap istekle birlikte geri gönderilir.
      const request = clarification
        ? { ...base, previous_question: clarification.question, clarification_answer: clarification.answer }
        : base
      abort.current?.abort()
      const controller = new AbortController()
      abort.current = controller
      setView({ name: 'loading' })
      try {
        const response = await createPlan(request, controller.signal, session?.access_token)
        if (isClarification(response)) {
          setView({ name: 'clarify', question: response.question })
        } else {
          // Hak yalnızca başarıyla üretilen planlarda düşer (soru dönüşü ve hatalar sayılmaz).
          if (!session) recordGuestPlan()
          setPlan(response)
          setView({ name: 'results' })
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        // Backend'in sunucu tarafı misafir kotası tetiklendiyse (localStorage
        // bastırılmış/silinmiş olsa bile) aynı "limit" ekranını göster.
        if (err instanceof ApiError && err.guestLimit) return setView({ name: 'limit' })
        setView({ name: 'error', error: err instanceof ApiError ? err : new ApiError(0, 'Beklenmeyen hata') })
      }
    },
    [prefs, session, authLoading],
  )

  const toPrefs = () => {
    abort.current?.abort()
    setView({ name: 'prefs' })
  }

  const openAccount = () => setView({ name: 'account', from: view })

  const onNav = (key: NavKey) => {
    if (key === 'discover') setView({ name: 'location' })
    else if (key === 'preferences') toPrefs()
    else if (plan) setView({ name: 'results' })
  }

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [view.name])

  // Link ile paylaşılan bir rota: Shell/view state machine'in tamamen dışında, bağımsız sayfa.
  if (sharedId) {
    return (
      <SharedPlanScreen
        planId={sharedId}
        session={session}
        onClose={() => {
          window.history.replaceState(null, '', window.location.pathname)
          setSharedId(null)
          setAccountKey((k) => k + 1)
        }}
        onCreateOwn={() => {
          window.history.replaceState(null, '', window.location.pathname)
          setSharedId(null)
          setView({ name: 'location' })
        }}
      />
    )
  }

  // Navigasyon tam ekran: üst başlık ve sekme çubuğu yok.
  if (view.name === 'navigate' && plan) {
    const alternative = plan.alternatives[view.index]
    return (
      <NavigationScreen
        alternative={alternative}
        planIndex={view.index}
        segments={buildSegments(alternative, view.approach)}
        onExit={() => setView({ name: 'detail', index: view.index })}
      />
    )
  }

  return (
    <Shell
      title={TITLES[view.name]}
      nav={NAV_FOR[view.name]}
      plansEnabled={plan !== null}
      onNav={onNav}
      onBack={
        view.name === 'detail'
          ? () => setView({ name: 'results' })
          : view.name === 'account'
            ? () => setView(view.from)
            : undefined
      }
      theme={theme}
      onToggleTheme={toggleTheme}
      loggedIn={session !== null}
      onAccount={openAccount}
    >
      {view.name === 'location' && (
        <LocationScreen
          prefs={prefs}
          onChange={setPrefs}
          onContinue={() => hasLocation(prefs) && setView({ name: 'prefs' })}
          onPickFrequent={(place) => {
            setPrefs((p) => ({ ...p, anchorPlace: place, cityInput: place.name }))
            setView({ name: 'prefs' })
          }}
          session={session}
        />
      )}
      {view.name === 'prefs' && <PreferencesScreen prefs={prefs} onChange={setPrefs} onSubmit={() => (hasLocation(prefs) ? submit() : setView({ name: 'location' }))} />}
      {view.name === 'loading' && <LoadingScreen prefs={prefs} onCancel={toPrefs} />}
      {view.name === 'limit' && <LimitScreen onLogin={openAccount} onBack={toPrefs} />}
      {view.name === 'clarify' && (
        <ClarifyScreen question={view.question} onAnswer={(answer) => submit({ question: view.question, answer })} onBack={toPrefs} />
      )}
      {view.name === 'error' && <ErrorBanner {...errorCopy(view.error)} onRetry={() => submit()} onBack={toPrefs} />}
      {view.name === 'results' && plan && (
        <ResultsScreen plan={plan} prefs={prefs} onOpen={(index) => setView({ name: 'detail', index })} onPrefs={toPrefs} />
      )}
      {view.name === 'detail' && plan && (
        <DetailScreen
          plan={plan}
          index={view.index}
          travelMode={prefs.travelMode}
          userLoc={userLoc}
          onRequestLocation={requestLocation}
          onSelect={(index) => setView({ name: 'detail', index })}
          onPrefs={toPrefs}
          onStartNavigation={(approach) => setView({ name: 'navigate', index: view.index, approach })}
          session={session}
          onRequireAccount={openAccount}
          onAlternativesChange={(patches) =>
            setPlan((p) =>
              p
                ? {
                    ...p,
                    alternatives: p.alternatives.map((a, i) => {
                      const patch = patches.find((x) => x.index === i)
                      return patch ? { ...a, stops: patch.stops, legs: patch.legs, routes_available: patch.routesAvailable } : a
                    }),
                  }
                : p,
            )
          }
        />
      )}
      {view.name === 'account' && (
        <AccountScreen
          key={accountKey}
          session={session}
          onOpenSaved={setSharedId}
          resetToken={resetToken}
          onResetDone={() => setResetToken(null)}
        />
      )}
    </Shell>
  )
}
