import { useEffect, useState, type ReactNode } from 'react'
import { Icon } from '../components/Icon'
import { BUDGETS, GROUPS, THEMES, TRAVEL_MODES } from '../meta'
import type { Preferences } from '../prefs'
import type { TravelMode } from '../types'

interface Props {
  prefs: Preferences
  onChange: (p: Preferences) => void
  onSubmit: () => void
}

const MAX_HOURS = 10

function Card({ icon, title, right, children }: { icon: string; title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <div className="bg-surface rounded-2xl p-4 shadow-sm flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="font-label-md text-label-md text-ink font-semibold flex items-center gap-2">
          <Icon name={icon} className="text-primary text-[20px]" />
          {title}
        </h3>
        {right}
      </div>
      {children}
    </div>
  )
}

function Collapsible({
  icon,
  title,
  badge,
  hint,
  children,
}: {
  icon: string
  title: string
  badge?: ReactNode
  hint?: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(true)
  return (
    <div className="bg-surface rounded-2xl p-4 shadow-sm flex flex-col gap-3">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full text-left"
      >
        <span className="flex items-center gap-2 font-label-md text-label-md text-ink font-semibold">
          <Icon name={icon} className="text-primary text-[20px]" />
          {title}
        </span>
        <span className="flex items-center gap-2">
          {badge}
          {hint && !badge && <span className="font-label-sm text-label-sm text-text-secondary">{hint}</span>}
          <Icon
            name="expand_more"
            className={`text-[20px] text-text-secondary transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          />
        </span>
      </button>
      {open && <div className="flex flex-col gap-2.5 pt-1">{children}</div>}
    </div>
  )
}

// Başlangıç saati öneri: bir sonraki tam saat.
function defaultStartTime(): string {
  const h = (new Date().getHours() + 1) % 24
  return `${String(h).padStart(2, '0')}:00`
}

// "HH:MM" + N saat -> "HH:MM" (gün içinde döner).
function addHours(time: string, hours: number): string {
  const [h, m] = time.split(':').map(Number)
  const total = (h * 60 + m + hours * 60 + 24 * 60) % (24 * 60)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

export function PreferencesScreen({ prefs, onChange, onSubmit }: Props) {
  const set = <K extends keyof Preferences>(key: K, value: Preferences[K]) => onChange({ ...prefs, [key]: value })
  const group = GROUPS.find((g) => g.value === prefs.group)!

  // Kullanıcı hiç dokunmadıysa önerilen saati gerçekten prefs'e yazar (sadece
  // gösterip arkada göndermemek kafa karıştırıyordu — ne görülüyorsa o gönderilir).
  useEffect(() => {
    if (prefs.startTime === null) set('startTime', defaultStartTime())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startTime = prefs.startTime ?? defaultStartTime()
  const endTime = addHours(startTime, prefs.duration)

  const toggleCategory = (key: string) =>
    set('categories', prefs.categories.includes(key) ? prefs.categories.filter((c) => c !== key) : [...prefs.categories, key])

  return (
    <div className="flex flex-col w-full pb-28">
      <section className="flex flex-col gap-1 mb-6">
        <div className="inline-flex items-center gap-1.5 self-start px-3 py-1 rounded-full bg-weather-good-bg text-tertiary font-label-sm text-label-sm">
          <Icon name="tune" fill className="text-[16px] text-weather-good" />
          <span>Hızlı Özelleştirme</span>
        </div>
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-ink tracking-tight mt-1">Plan Tercihleri</h2>
        <p className="font-body-md text-body-md text-text-secondary leading-relaxed">
          Bugün nasıl bir gün geçirmek istersiniz? Tercihler opsiyoneldir.
        </p>
      </section>

      <form
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault()
          onSubmit()
        }}
      >
        <Collapsible
          icon="group"
          title="1. Grup Tipi"
          badge={
            <span className="px-2.5 py-1 rounded-full bg-weather-good-bg text-primary font-label-sm text-label-sm font-medium flex items-center gap-1">
              <Icon name={group.icon} className="text-[16px]" />
              {group.label}
            </span>
          }
        >
          <div className="flex items-center justify-between text-text-secondary font-label-sm text-label-sm px-0.5">
            <span>Seçim yapınız</span>
            <span className="text-[11px] text-text-secondary/80">Yana kaydırın →</span>
          </div>
          <div role="radiogroup" aria-label="Grup tipi" className="flex items-center gap-2 overflow-x-auto pb-1.5 pt-0.5 -mx-1 px-1">
            {GROUPS.map((g) => {
              const on = prefs.group === g.value
              return (
                <button
                  type="button"
                  key={g.value}
                  role="radio"
                  aria-checked={on}
                  onClick={() => set('group', g.value)}
                  className={`flex-shrink-0 flex items-center gap-2 px-3.5 py-2.5 rounded-xl font-label-md text-label-md transition-all active:scale-95 ${
                    on ? 'bg-primary text-on-primary shadow-sm' : 'bg-surface-container-low text-ink hover:bg-surface-variant'
                  }`}
                >
                  <Icon name={g.icon} className={`text-[18px] ${on ? 'text-on-primary' : 'text-text-secondary'}`} />
                  <span>{g.label}</span>
                  {on && <Icon name="check" className="text-[16px] text-on-primary ml-0.5" />}
                </button>
              )
            })}
          </div>
        </Collapsible>

        <Card
          icon="schedule"
          title="2. Ne kadar vaktiniz var?"
          right={
            <label className="flex items-center gap-1 font-label-sm text-label-sm text-primary font-medium">
              <span className="sr-only">Başlangıç saati</span>
              <input
                type="time"
                value={startTime}
                onChange={(e) => set('startTime', e.target.value)}
                className="bg-transparent text-primary font-label-sm text-label-sm font-medium focus:outline-none"
              />
              <span>- {endTime}</span>
            </label>
          }
        >
          <div className="flex items-center justify-between bg-surface-container-low p-2.5 rounded-xl">
            <button
              type="button"
              aria-label="Süreyi azalt"
              disabled={prefs.duration <= 1}
              onClick={() => set('duration', prefs.duration - 1)}
              className="w-12 h-12 rounded-xl bg-surface flex items-center justify-center text-ink shadow-sm active:scale-95 transition-transform disabled:opacity-40"
            >
              <Icon name="remove" className="text-[22px]" />
            </button>
            <div className="flex flex-col items-center">
              <output className="font-headline-lg-mobile text-headline-lg-mobile text-ink tracking-tight font-bold">
                {prefs.duration} saat
              </output>
              <span className="font-body-sm text-body-sm text-text-secondary">Tahmini rota akışı</span>
            </div>
            <button
              type="button"
              aria-label="Süreyi artır"
              disabled={prefs.duration >= MAX_HOURS}
              onClick={() => set('duration', prefs.duration + 1)}
              className="w-12 h-12 rounded-xl bg-surface flex items-center justify-center text-ink shadow-sm active:scale-95 transition-transform disabled:opacity-40"
            >
              <Icon name="add" className="text-[22px]" />
            </button>
          </div>
        </Card>

        <Card icon="payments" title="3. Bütçe" right={<span className="font-label-sm text-label-sm text-text-secondary">Opsiyonel</span>}>
          <div role="radiogroup" aria-label="Bütçe" className="grid grid-cols-4 gap-1 bg-surface-container-low p-1 rounded-xl">
            {BUDGETS.map((b) => {
              const on = prefs.budget === b.value
              return (
                <button
                  type="button"
                  key={b.label}
                  role="radio"
                  aria-checked={on}
                  onClick={() => set('budget', b.value)}
                  className={`h-10 rounded-lg font-label-md text-label-md transition-all ${
                    on ? 'bg-surface text-ink font-semibold shadow-sm' : 'text-text-secondary'
                  }`}
                >
                  {b.label}
                </button>
              )
            })}
          </div>
        </Card>

        <Collapsible icon="local_activity" title="4. Aktivite Türü" hint="Çoklu seçim">
          <div className="flex flex-wrap gap-2.5">
            {THEMES.map((t) => {
              const on = prefs.categories.includes(t.key)
              return (
                <button
                  type="button"
                  key={t.key}
                  aria-pressed={on}
                  onClick={() => toggleCategory(t.key)}
                  className={`inline-flex items-center gap-2 h-11 px-4 rounded-full font-label-md text-label-md transition-all active:scale-95 ${
                    on ? 'bg-plan-a text-on-primary shadow-sm' : 'bg-surface-container-low text-ink'
                  }`}
                >
                  <Icon name={t.icon} className={`text-[18px] ${on ? 'text-on-primary' : 'text-text-secondary'}`} />
                  <span>{t.label}</span>
                  {on && <Icon name="check" className="text-[16px]" />}
                </button>
              )
            })}
          </div>
        </Collapsible>

        <Card icon="directions" title="5. Ulaşım Şekli">
          <div role="radiogroup" aria-label="Ulaşım şekli" className="grid grid-cols-3 gap-1 bg-surface-container-low p-1 rounded-xl">
            {(Object.keys(TRAVEL_MODES) as TravelMode[]).map((m) => {
              const on = prefs.travelMode === m
              return (
                <button
                  type="button"
                  key={m}
                  role="radio"
                  aria-checked={on}
                  onClick={() => set('travelMode', m)}
                  className={`h-14 rounded-lg flex flex-col items-center justify-center gap-0.5 font-label-sm text-label-sm transition-all ${
                    on ? 'bg-surface text-ink font-semibold shadow-sm' : 'text-text-secondary'
                  }`}
                >
                  <Icon name={TRAVEL_MODES[m].icon} className="text-[20px]" />
                  {TRAVEL_MODES[m].label}
                </button>
              )
            })}
          </div>
        </Card>

        <div className="bg-surface rounded-2xl p-4 shadow-sm flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label htmlFor="custom-prompt" className="font-label-md text-label-md text-ink flex items-center gap-2 font-semibold">
              <Icon name="edit_note" className="text-primary text-[20px]" />
              6. Ekstra Not veya İstekler
            </label>
            <span className="font-label-sm text-label-sm text-text-secondary">Opsiyonel</span>
          </div>
          <textarea
            id="custom-prompt"
            rows={3}
            value={prefs.note}
            onChange={(e) => set('note', e.target.value)}
            placeholder="Ailecek 4 saatimiz var, çocuklarla açık havada keyifli vakit geçirip sakin bir kafede dinlenmek istiyoruz."
            className="w-full bg-surface-container-low text-ink placeholder:text-text-secondary/70 rounded-xl p-3 text-body-md font-body-md focus:outline-none focus:bg-surface transition-all resize-none"
          />
          <div className="flex items-center gap-1.5 px-1 text-text-secondary">
            <Icon name="magic_button" className="text-[16px] text-primary" />
            <span className="font-body-sm text-body-sm">Yapay zeka bu notu plan oluştururken önceliklendirecektir.</span>
          </div>
        </div>
      </form>

      <div className="fixed bottom-16 left-0 right-0 z-40 bg-gradient-to-t from-background via-background/95 to-transparent pt-4 pb-3 px-margin">
        <div className="max-w-md mx-auto">
          <button
            type="button"
            onClick={onSubmit}
            className="w-full h-[52px] rounded-2xl bg-plan-a hover:bg-primary-strong active:bg-primary-strong text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2 shadow-lg transition-transform active:scale-[0.99]"
          >
            <Icon name="auto_awesome" className="text-[22px]" />
            <span>Plan Oluştur</span>
          </button>
        </div>
      </div>
    </div>
  )
}
