interface Props {
  name: string
  className?: string
  fill?: boolean
}

export function Icon({ name, className = '', fill = false }: Props) {
  return (
    <span className={`material-symbols-outlined ${fill ? 'fill' : ''} ${className}`} aria-hidden>
      {name}
    </span>
  )
}
