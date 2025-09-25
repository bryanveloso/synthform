import { useTimeline } from '@/hooks/use-timeline'
import { getEventComponent } from '@/components/shared/timeline/events'
import {
  ChatNotification,
  Cheer,
  Follow,
  RedemptionAdd,
} from './item'

export const Timeline = () => {
  const { events: timelineEvents } = useTimeline(10)

  return (
    <div className="bg-shark-960 absolute right-0 bottom-0 left-0 h-12 w-full p-1 text-xs text-white">
      <div className="flex gap-1">
        {timelineEvents.map((event) => {
          const component = getEventComponent(event, {
            ChatNotification,
            Cheer,
            Follow,
            RedemptionAdd,
          })
          if (!component) return null

          return (
            <div
              key={event.id}
              className={`from-shark-880 to-shark-920 rounded-sm bg-gradient-to-b px-4 shadow-xl/50 inset-ring inset-ring-white/5`}>
              <div className="text-base">{component}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
