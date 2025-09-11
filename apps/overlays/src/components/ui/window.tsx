import type { FC, PropsWithChildren } from "react"

const Frame: FC<PropsWithChildren<{ toolbar?: boolean }>> = ({ children, toolbar = false }) => {
  return (
    <div
      className={`from-shark-880 to-shark-920 rounded-lg bg-gradient-to-b p-3 shadow-xl/50 inset-ring-2 inset-ring-white/10 ${toolbar ? 'pt-0' : ''}`}>
      {children}
    </div>
  )
}

const Circle: FC<PropsWithChildren> = ({ children }) => {
  return <div className="relative h-3 w-3 overflow-hidden rounded-full inset-ring-3 inset-ring-shark-760">{children}</div>
}

const Toolbar: FC<PropsWithChildren> = ({ children }) => {
  return (<div className="flex items-center gap-2 py-2">{children}</div>)
}

const Slot: FC<PropsWithChildren> = ({ children }) => {
  return <div className="slot">{children}</div>
}

export {
  Circle,
  Frame,
  Toolbar,
  Slot
}
