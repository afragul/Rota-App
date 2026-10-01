import { Icon } from './Icon'

interface Props {
  title: string
  message?: string
  onRetry?: () => void
  onBack?: () => void
}

export function ErrorBanner({ title, message, onRetry, onBack }: Props) {
  return (
    <div className="flex flex-col gap-space-lg pt-space-lg">
      <div className="w-full bg-error-container/60 rounded-xl p-space-md shadow-sm flex items-start gap-space-sm" role="alert">
        <div className="w-8 h-8 rounded-full bg-error/15 flex items-center justify-center shrink-0 mt-0.5">
          <Icon name="warning" className="text-error text-[18px]" />
        </div>
        <div className="flex flex-col min-w-0">
          <h2 className="font-label-lg text-label-lg text-error font-bold">{title}</h2>
          {message && <p className="font-body-sm text-body-sm text-on-error-container leading-tight mt-0.5">{message}</p>}
        </div>
      </div>
      <div className="flex flex-col gap-space-sm">
        {onRetry && (
          <button
            onClick={onRetry}
            className="w-full h-[52px] rounded-2xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2 shadow-sm active:scale-[0.99] transition-transform"
          >
            <Icon name="refresh" className="text-[20px]" />
            Tekrar Dene
          </button>
        )}
        {onBack && (
          <button
            onClick={onBack}
            className="w-full h-12 rounded-xl bg-surface text-ink font-label-md text-label-md flex items-center justify-center gap-space-xs shadow-sm active:bg-surface-container-low"
          >
            <Icon name="tune" className="text-[18px]" />
            Tercihleri Değiştir
          </button>
        )}
      </div>
    </div>
  )
}
