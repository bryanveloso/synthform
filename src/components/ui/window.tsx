import { forwardRef, type PropsWithChildren } from 'react'

import { cn } from '@/lib/utils'

const Frame = forwardRef<
  HTMLDivElement,
  PropsWithChildren<{ className?: string; toolbar?: boolean }>
>(({ children, className, toolbar = false }, ref) => {
  return (
    <div
      ref={ref}
      className={cn(
        `from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-3 shadow-xl/50 inset-ring-2 inset-ring-white/10`,
        { 'pt-0': toolbar },
        className,
      )}>
      {children}
    </div>
  )
})
Frame.displayName = 'Frame'

const Circle = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string }>>(
  ({ children, className }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'inset-ring-shark-760 relative h-3 w-3 overflow-hidden rounded-full inset-ring-3',
          className,
        )}>
        {children}
      </div>
    )
  },
)
Circle.displayName = 'Circle'

const Toolbar = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string }>>(
  ({ children, className }, ref) => {
    return (
      <div ref={ref} className={cn('flex items-center gap-2 py-2', className)}>
        {children}
      </div>
    )
  },
)
Toolbar.displayName = 'Toolbar'

const Slot = forwardRef<HTMLDivElement, PropsWithChildren<{ className?: string }>>(
  ({ children, className }, ref) => {
    return (
      <div ref={ref} className={cn('slot', className)}>
        {children}
      </div>
    )
  },
)
Slot.displayName = 'Slot'

export { Circle, Frame, Toolbar, Slot }
