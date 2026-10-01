import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, createPlan } from './api'
import { ErrorBanner } from './components/ErrorBanner'
import { Shell, type NavKey } from './components/Shell'
import { DEFAULT_PREFS, hasLocation, toRequest, type Preferences } from './prefs'
import { ClarifyScreen } from './screens/ClarifyScreen'
import { DetailScreen } from './screens/DetailScreen'
import { LoadingScreen } from './screens/LoadingScreen'
import { LocationScreen } from './screens/LocationScreen'
import { PreferencesScreen } from './screens/PreferencesScreen'
import { ResultsScreen } from './screens/ResultsScreen'
import { isClarification, type DayPlan } from './types'

type View =
  | { name: 'location' }
  | { name: 'prefs' }
  | { name: 'loading' }
  | { name: 'clarify'; question: string }
  | { name: 'error'; error: ApiError }
  | { name: 'results' }
  | { name: 'detail'; index: number }

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
}

const NAV_FOR: Record<View['name'], NavKey> = {
  location: 'discover',
  prefs: 'preferences',
  clarify: 'preferences',
  loading: 'plans',
  error: 'plans',
  results: 'plans',
  detail: 'plans',
}

export default function App() {
  // Tercihler ve son plan ekranlar arasında korunur.
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS)
  const [plan, setPlan] = useState<DayPlan | null>(null)
  const [view, setView] = useState<View>({ name: 'location' })
  const abort = useRef<AbortController | null>(null)

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
        <DetailScreen plan={plan} index={view.index} onSelect={(index) => setView({ name: 'detail', index })} onPrefs={toPrefs} />
      )}
    </Shell>
  )
}
