import type { ReactElement } from 'react'
import type {
  TimelineEvent,
  ChatNotificationEvent,
  CheerEvent,
  ChannelFollowEvent,
} from '@/types/events'

export interface EventComponents {
  ChatNotification: React.ComponentType<{ event: ChatNotificationEvent }>
  Cheer: React.ComponentType<{ event: CheerEvent }>
  Follow: React.ComponentType<{ event: ChannelFollowEvent }>
}

export const getEventComponent = (
  event: TimelineEvent,
  components: EventComponents,
): ReactElement | null => {
  switch (event.type) {
    case 'twitch.channel.chat.notification':
      return <components.ChatNotification event={event} />
    case 'twitch.channel.cheer':
      return <components.Cheer event={event} />
    case 'twitch.channel.follow':
      return <components.Follow event={event} />
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
