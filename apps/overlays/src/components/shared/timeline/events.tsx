import type { ReactElement } from 'react'
import type {
  TimelineEvent,
  ChatNotificationEvent,
  CheerEvent,
  ChannelFollowEvent,
  ChannelPointsRedemptionEvent,
} from '@/types/events'

export interface EventComponents {
  ChatNotification: React.ComponentType<{ event: ChatNotificationEvent }>
  Cheer: React.ComponentType<{ event: CheerEvent }>
  Follow: React.ComponentType<{ event: ChannelFollowEvent }>
  RedemptionAdd: React.ComponentType<{ event: ChannelPointsRedemptionEvent }>
}

export const getEventComponent = (
  event: TimelineEvent,
  components: EventComponents
): ReactElement | null => {
  switch (event.type) {
    case 'twitch.channel.chat.notification':
      return <components.ChatNotification event={event} />
    case 'twitch.channel.cheer':
      return <components.Cheer event={event} />
    case 'twitch.channel.follow':
      return <components.Follow event={event} />
    case 'twitch.channel.channel_points_custom_reward_redemption.add':
      return <components.RedemptionAdd event={event} />
    // Legacy event types that are now handled by chat.notification
    case 'twitch.channel.subscribe':
    case 'twitch.channel.subscription.gift':
    case 'twitch.channel.subscription.message':
    case 'twitch.channel.raid':
      return null // These are now handled via chat.notification
    default:
      return null
  }
}