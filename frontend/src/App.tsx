import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, createPlan, type LatLng } from './api'
import { ErrorBanner } from './components/ErrorBanner'
import { Shell, type NavKey } from './components/Shell'
import { DEFAULT_PREFS, hasLocation, toRequest, type Preferences } from './prefs'
import { ClarifyScreen } from './screens/ClarifyScreen'
import { DetailScreen, type UserLocation } from './screens/DetailScreen'
import { NavigationScreen } from './screens/NavigationScreen'
import { LoadingScreen } from './screens/LoadingScreen'
import { LocationScreen } from './screens/LocationScreen'
import { PreferencesScreen } from './screens/PreferencesScreen'
import { ResultsScreen } from './screens/ResultsScreen'
import { buildSegments } from './nav'
import { isClarification, type ApproachRoute, type DayPlan } from './types'

type View =
  | { name: 'location' }
  | { name: 'prefs' }
  | { name: 'loading' }
  | { name: 'clarify'; question: string }
  | { name: 'error'; error: ApiError }
  | { name: 'results' }
  | { name: 'detail'; index: number }
  | { name: 'navigate'; index: number; approach: ApproachRoute }

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
  clarify: 'Rota Oluştur',
  error: 'Günlük Planlar',
  results: 'Günlük Planlar',
  detail: 'Plan Detayı',
  navigate: 'Navigasyon',
}

const NAV_FOR: Record<View['name'], NavKey> = {
  location: 'discover',
  prefs: 'preferences',
  clarify: 'preferences',
  loading: 'plans',
  error: 'plans',
  results: 'plans',
  detail: 'plans',
  navigate: 'plans',
}

export default function App() {
  // Tercihler ve son plan ekranlar arasında korunur.
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS)
  const [plan, setPlan] = useState<DayPlan | null>(null)
  const [view, setView] = useState<View>({ name: 'location' })
  const [userLoc, setUserLoc] = useState<UserLocation>({ status: 'idle' })
  const abort = useRef<AbortController | null>(null)

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
      // Backend stateless: soru ve cevap istekle birlikte geri gönderilir.
      const request = clarification
        ? { ...base, previous_question: clarification.question, clarification_answer: clarification.answer }
        : base
      abort.current?.abort()
      const controller = new AbortController()
      abort.current = controller
      setView({ name: 'loading' })
      try {
        const response = await createPlan(request, controller.signal)
        if (isClarification(response)) {
          setView({ name: 'clarify', question: response.question })
        } else {
          setPlan(response)
          setView({ name: 'results' })
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setView({ name: 'error', error: err instanceof ApiError ? err : new ApiError(0, 'Beklenmeyen hata') })
      }
    },
    [prefs],
  )

  const toPrefs = () => {
    abort.current?.abort()
    setView({ name: 'prefs' })
  }

  const onNav = (key: NavKey) => {
    if (key === 'discover') setView({ name: 'location' })
    else if (key === 'preferences') toPrefs()
    else if (plan) setView({ name: 'results' })
  }

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [view.name])

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
      onBack={view.name === 'detail' ? () => setView({ name: 'results' }) : undefined}
    >
      {view.name === 'location' && (
        <LocationScreen
          prefs={prefs}
          onChange={setPrefs}
          onContinue={() => hasLocation(prefs) && setView({ name: 'prefs' })}
        />
      )}
      {view.name === 'prefs' && <PreferencesScreen prefs={prefs} onChange={setPrefs} onSubmit={() => (hasLocation(prefs) ? submit() : setView({ name: 'location' }))} />}
      {view.name === 'loading' && <LoadingScreen prefs={prefs} onCancel={toPrefs} />}
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
        />
      )}
    </Shell>
  )
}
