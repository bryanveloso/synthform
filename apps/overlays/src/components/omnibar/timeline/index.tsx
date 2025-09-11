import { useState, useEffect } from 'react'

import { useServer } from '@/hooks/use-server'
import type { TimelineEvent } from '@/types/events'

import { Cheer, Follow, Subscription, SubscriptionGift, SubscriptionMessage, RedemptionAdd, Raid } from './item'

const MESSAGE_TYPES = ['timeline:sync', 'timeline:push'] as const

const getType = (event: TimelineEvent) => {
  switch (event.type) {
    case 'twitch.channel.follow':
      return <Follow event={event} />
    case 'twitch.channel.subscribe':
      return <Subscription event={event} />
    case 'twitch.channel.subscription.gift':
      return <SubscriptionGift event={event} />
    case 'twitch.channel.subscription.message':
      return <SubscriptionMessage event={event} />
    case 'twitch.channel.cheer':
      return <Cheer event={event} />
    case 'twitch.channel.channel_points_custom_reward_redemption.add':
      return <RedemptionAdd event={event} />
    case 'twitch.channel.raid':
      return <Raid event={event} />
    default:
      return null
  }
}

export const Timeline = () => {
  const { data } = useServer(MESSAGE_TYPES)
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([])

  const timelinePush = data['timeline:push']
  const timelineSync = data['timeline:sync']

  useEffect(() => {
    if (timelineSync) {
      const events: TimelineEvent[] = Array.isArray(timelineSync) ? timelineSync : [timelineSync]
      setTimelineEvents(events)
    }
  }, [timelineSync])

  useEffect(() => {
    if (timelinePush) {
      setTimelineEvents((prev) => [timelinePush as TimelineEvent, ...prev])
    }
  }, [timelinePush])

  return (
    <div className="bg-shark-960 absolute right-0 bottom-0 left-0 h-12 w-full p-1 text-xs text-white">
      <div className="flex gap-1">
        {timelineEvents.map((event) => {
          const component = getType(event)
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
