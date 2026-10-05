import { Icon } from '../components/Icon'
import { GUEST_PLAN_LIMIT } from '../guestLimit'

interface Props {
  onLogin: () => void
  onBack: () => void
}

export function LimitScreen({ onLogin, onBack }: Props) {
  return (
    <div className="flex flex-col gap-space-lg pt-space-lg">
      <div className="w-full bg-surface rounded-xl p-space-md shadow-sm flex items-start gap-space-sm" role="status">
        <div className="w-8 h-8 rounded-full bg-plan-a/15 flex items-center justify-center shrink-0 mt-0.5">
          <Icon name="lock" className="text-plan-a text-[18px]" />
        </div>
        <div className="flex flex-col min-w-0">
          <h2 className="font-label-lg text-label-lg text-ink font-bold">Ücretsiz hakkın doldu</h2>
          <p className="font-body-sm text-body-sm text-ink leading-tight mt-0.5">
            Hesap açmadan {GUEST_PLAN_LIMIT} rota oluşturabilirsin. Devam etmek için giriş yap ya da hesap oluştur.
          </p>
        </div>
      </div>
      <div className="flex flex-col gap-space-sm">
        <button
          onClick={onLogin}
          className="w-full h-[52px] rounded-2xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2 shadow-sm active:scale-[0.99] transition-transform"
        >
          <Icon name="person" className="text-[20px]" />
          Giriş Yap / Kayıt Ol
        </button>
        <button
          onClick={onBack}
          className="w-full h-12 rounded-xl bg-surface text-ink font-label-md text-label-md flex items-center justify-center gap-space-xs shadow-sm active:bg-surface-container-low"
        >
          <Icon name="tune" className="text-[18px]" />
          Tercihleri Değiştir
        </button>
      </div>
    </div>
  )
}
