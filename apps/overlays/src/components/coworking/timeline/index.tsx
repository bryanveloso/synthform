import { useTimeline } from '@/hooks/use-timeline'
import type { TimelineEvent } from '@/types/events'

import { Cheer, Follow, Subscription, SubscriptionGift, SubscriptionMessage, RedemptionAdd, Raid } from './item'

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
  const { events: timelineEvents } = useTimeline(15)

  return (
    <div className="overflow-x-hidden relative ">
      <div className='absolute right-0 bg-gradient-to-r from-transparent to-shark-960 w-48 h-full'></div>
      <div className="flex gap-2 items-center pl-6">
        <div className='inset-ring-1 inset-ring-white/5 outline-1 p-2 rounded-sm bg-gradient-to-b from-shark-880 to-shark-920'>
          <svg
            version="1.1"
            id="Arrow-Right-1--Streamline-Streamline-3.0"
            xmlns="http://www.w3.org/2000/svg"
            xmlnsXlink="http://www.w3.org/1999/xlink"
            x="0"
            y="0"
            viewBox="0 0 24 24"
            xmlSpace="preserve"
            enableBackground="new 0 0 24 24"
            className="text-lime size-3">
            <path
              d="M19.5 12c0 0.7 -0.3 1.3 -0.8 1.7L7.5 23.6c-0.8 0.7 -2 0.6 -2.6 -0.2 -0.6 -0.8 -0.6 -1.9 0.2 -2.6l9.8 -8.6c0.1 -0.1 0.1 -0.2 0 -0.4L5.1 3.2c-0.8 -0.7 -0.8 -1.9 -0.1 -2.6 0.7 -0.7 1.8 -0.8 2.6 -0.2l11.2 9.8c0.4 0.5 0.7 1.1 0.7 1.8z"
              fill="currentColor"
              strokeWidth="1"></path>
          </svg>
        </div>
        {timelineEvents.map((event) => {
          const component = getType(event)
          if (!component) return null

          return (
            <div key={event.id} className="font-sans text-sm text-white">
              {component}
            </div>
          )
        })}
      </div>
    </div>
  )
}
