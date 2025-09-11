import { useState, useEffect } from 'react'

import { useServer } from '@/hooks/use-server'
import type {
  TimelineEvent,
  ChannelFollowEvent,
  ChannelSubscribeEvent,
  ChannelSubscriptionGiftEvent,
  ChannelSubscriptionMessageEvent,
  ChannelCheerEvent,
  ChannelPointsRedemptionEvent,
  ChannelRaidEvent,
} from '@/types/events'

const MESSAGE_TYPES = ['timeline:sync', 'timeline:push'] as const

const OOF_ID = '5685d03e-80c2-4640-ba06-566fb8bbc4ce'

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

const Follow = ({ event }: { event: ChannelFollowEvent }) => (
  <div>
    <div className="font-caps">Follow</div>
    <div>{event.data.payload.user_display_name || event.data.user_name}</div>
  </div>
)

const Subscription = ({ event }: { event: ChannelSubscribeEvent }) => (
  <div>
    <div className="font-caps">Subscription</div>
    <div>{event.data.payload.user_display_name || event.data.user_name}</div>
  </div>
)

const SubscriptionGift = ({ event }: { event: ChannelSubscriptionGiftEvent }) => (
  <div>
    <div className="font-caps">Gift</div>
    <div>
      {event.data.payload.user_display_name || event.data.user_name} × {event.data.payload.total}
    </div>
  </div>
)

const SubscriptionMessage = ({ event }: { event: ChannelSubscriptionMessageEvent }) => (
  <div>
    <div className="font-caps">Resub</div>
    <div>
      {event.data.payload.user_display_name || event.data.user_name} × {event.data.payload.cumulative_months}
    </div>
  </div>
)

const Cheer = ({ event }: { event: ChannelCheerEvent }) => (
  <div>
    <div className="font-caps">Cheer</div>
    <div>
      {event.data.payload.is_anonymous
        ? 'Anonymous'
        : event.data.payload.user_display_name || event.data.payload.user_name || 'Unknown'}{' '}
      × {event.data.payload.bits}
    </div>
  </div>
)

const RedemptionAdd = ({ event }: { event: ChannelPointsRedemptionEvent }) => (
  <div>
    <div className="font-caps">{event.data.payload.reward.title}</div>
    <div>{event.data.payload.user_display_name || event.data.user_name}</div>
  </div>
)

const Raid = ({ event }: { event: ChannelRaidEvent }) => (
  <div>
    <div className="font-caps">Raid</div>
    <div>
      {event.data.payload.from_broadcaster_user_display_name} × {event.data.payload.viewers}
    </div>
  </div>
)

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
              className={`from-shark-880 to-shark-920 rounded-sm bg-gradient-to-b p-2 px-4 shadow-xl/50 inset-ring inset-ring-white/5`}>
              <div className="text-base">{component}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
