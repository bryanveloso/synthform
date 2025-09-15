import { cn } from '@/lib/utils'
import { useStatus } from '@/hooks/use-status'

const STATUSES = {
  online: {
    color: 'from-lime to-lime/50',
    textColor: 'text-lime',
    defaultMessage: 'online',
  },
  away: {
    color: 'from-marigold to-marigold/50',
    textColor: 'text-marigold',
    defaultMessage: 'away',
  },
  busy: {
    color: 'from-rose-500 to-rose-500/50',
    textColor: 'text-rose-500',
    defaultMessage: 'busy',
  },
  brb: {
    color: 'from-sky to-sky/50',
    textColor: 'text-sky',
    defaultMessage: 'taking a break',
  },
  focus: {
    color: 'from-royal to-royal/50',
    textColor: 'text-royal',
    defaultMessage: 'in focus mode',
  },
}

export function Status() {
  const { status } = useStatus()

  // Default to online if status is not in config
  const config = STATUSES[status.status] || STATUSES.online
  const displayMessage = status.message || config.defaultMessage

  return (
    <div className="relative flex rounded-lg bg-gradient-to-b shadow-xl/50">
      <div className="absolute top-0 left-0 h-full w-full rounded-lg inset-ring-2 inset-ring-white/10"></div>

      <div className="from-shark-840 to-shark-880 flex items-center justify-center rounded-l-lg bg-gradient-to-b pr-4 pl-4.5">
        <div
          className={cn(
            'outline-shark-920 size-3.5 rounded-full bg-radial-[at_50%_25%] outline-4',
            config.color,
          )}></div>
      </div>
      <div className="from-shark-880 to-shark-920 text-shark-240 flex-1 rounded-r-lg bg-gradient-to-b p-3 font-sans text-shadow-sm/50">
        Bryan is currently{' '}
        <span className={cn('font-bold', config.textColor)}>{displayMessage}</span>.
      </div>
    </div>
  )
}
