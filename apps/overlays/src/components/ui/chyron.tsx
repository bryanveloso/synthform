import { forwardRef, type PropsWithChildren } from 'react'

import { cn } from '@/lib/utils'

const Event = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string }>>(
  ({ className, children }, ref) => {
    return (
      <div ref={ref} className={cn('font-caps text-shark-560 -mt-2 whitespace-nowrap', className)}>
        {children}
      </div>
    )
  },
)
Event.displayName = 'Event'

const Frame = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string; style?: React.CSSProperties }>>(
  ({ className, children, style }, ref) => {
    return (
      <div
        ref={ref}
        style={style}
        className={cn(
          'relative flex h-16 min-w-0 items-center overflow-x-hidden',
          'bg-shark-960',
          className,
        )}>
        {children}
      </div>
    )
  },
)
Frame.displayName = 'Frame'

const Item = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string }>>(
  ({ className, children }, ref) => {
    return (
      <div ref={ref} className={cn('', className)}>
        {children}
      </div>
    )
  },
)
Item.displayName = 'Item'

const Username = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string }>>(
  ({ className, children }, ref) => {
    return (
      <div
        ref={ref}
        className={cn('text-md font-sans font-bold whitespace-nowrap text-white', className)}>
        {children}
      </div>
    )
  },
)
Username.displayName = 'Username'


export { Event, Frame, Item, Username }
