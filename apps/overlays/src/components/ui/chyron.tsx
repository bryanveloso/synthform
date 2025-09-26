import { forwardRef, type PropsWithChildren } from 'react'

import { cn } from '@/lib/utils'

const Frame = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string }>>(
  ({ className, children }, ref) => {
    return (
      <div
        ref={ref}
        className={cn('relative h-16 flex items-center min-w-0 overflow-x-hidden', 'bg-shark-960', className)}>
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
      <div ref={ref} className={cn('font-sans text-md font-bold text-white', className)}>
        {children}
      </div>
    )
  },
)
Username.displayName = 'Username'

const Event = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string }>>(
  ({ className, children }, ref) => {
    return (
      <div ref={ref} className={cn('font-caps text-shark-560 whitespace-nowrap -mt-2', className)}>
        {children}
      </div>
    )
  },
)
Event.displayName = 'Event'

export { Event, Frame, Item, Username }
