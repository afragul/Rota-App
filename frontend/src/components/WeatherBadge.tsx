import type { DayPlan } from '../types'
import { Icon } from './Icon'

// Hava durumu rozeti: açık/karma, yağışlı/indoor ve bilinmiyor olmak üzere 3 varyant.
export function WeatherBadge({ plan }: { plan: DayPlan }) {
  const w = plan.weather
  if (!plan.weather_available || !w) {
    return (
      <div className="w-full bg-weather-unknown-bg rounded-lg px-space-md py-2 flex items-center gap-space-sm" role="status">
        <Icon name="cloud_off" className="text-weather-unknown text-[18px] shrink-0" />
        <p className="font-body-sm text-body-sm text-text-secondary">
          <span className="font-semibold text-weather-unknown">Veri Alınamadı:</span> Planlar hava açık varsayılarak
          üretildi.
        </p>
      </div>
    )
  }

  if (w.is_bad) {
    return (
      <div className="w-full bg-weather-bad-bg rounded-xl p-space-md shadow-sm flex items-center gap-space-sm" role="status">
        <div className="w-9 h-9 rounded-full bg-surface/80 flex items-center justify-center shrink-0">
          <Icon name="rainy" fill className="text-weather-bad text-[22px]" />
        </div>
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-headline-md text-headline-md text-ink leading-none">{Math.round(w.temperature)}°C</span>
            <span className="font-label-sm text-label-sm text-ink font-semibold capitalize">{w.condition}</span>
          </div>
          <p className="font-body-sm text-body-sm text-text-secondary mt-0.5">Kapalı mekân ağırlıklı rotalar hazırlandı</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full bg-weather-good-bg rounded-xl p-space-md shadow-sm flex items-center gap-space-sm" role="status">
      <div className="w-9 h-9 rounded-full bg-surface/80 flex items-center justify-center shrink-0">
        <Icon name="wb_sunny" fill className="text-weather-good text-[22px]" />
      </div>
      <div className="flex flex-col min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="font-headline-md text-headline-md text-ink leading-none">{Math.round(w.temperature)}°C</span>
          <span className="font-label-sm text-label-sm text-ink font-semibold capitalize">{w.condition}</span>
        </div>
        <p className="font-body-sm text-body-sm text-text-secondary mt-0.5">Karma açık ve kapalı alan önerileri</p>
      </div>
    </div>
  )
}
