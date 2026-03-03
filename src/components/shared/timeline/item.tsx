import { Event, Username } from '@/components/ui/chyron'
import type { ChannelFollowEvent, ChatNotificationEvent, CheerEvent } from '@/types/events'

// Mega component for handling all chat notification events
export const ChatNotification = ({ event }: { event: ChatNotificationEvent }) => {
  const payload = event.data.payload
  const { notice_type, chatter_display_name, chatter_user_name } = payload

  switch (notice_type) {
    case 'sub':
      return (
        <>
          <Username>{chatter_display_name || chatter_user_name}</Username>
          <Event>New Subscription</Event>
        </>
      )

    case 'resub':
      return (
        <>
          <Username>{chatter_display_name || chatter_user_name}</Username>
          <Event>
            <span className="text-lime">{payload.resub?.cumulative_months || '?'}</span> Months
          </Event>
        </>
      )

    case 'sub_gift':
      return (
        <>
          <Username>
            {payload.sub_gift?.recipient?.display_name ||
              payload.sub_gift?.recipient?.name ||
              'Unknown'}
          </Username>
          <Event>Gift Recipient</Event>
        </>
      )

    case 'community_sub_gift':
      return (
        <>
          <Username>{chatter_display_name || chatter_user_name}</Username>
          <Event>
            Gifted <span className="text-lime">×{payload.community_sub_gift?.total || '?'}</span>
          </Event>
        </>
      )

    case 'raid':
      return (
        <>
          <Username>
            {payload.raid?.user?.display_name ||
              payload.raid?.user?.name ||
              chatter_display_name ||
              chatter_user_name}{' '}
            + {payload.raid?.viewer_count || '?'}
          </Username>
          <Event>Raid</Event>
        </>
      )

    case 'bits_badge_tier':
      return (
        <>
          <Username>{chatter_display_name || chatter_user_name}</Username>
          <Event>Bits Badge {payload.bits_badge_tier?.tier || ''}</Event>
        </>
      )

    case 'charity_donation':
      return (
        <>
          <Username>{chatter_display_name || chatter_user_name}</Username>
          <Event>${payload.charity_donation?.amount.value || '?'} Charity</Event>
        </>
      )

    default:
      // Fallback for unknown notice types
      return (
        <>
          <Username>{chatter_display_name || chatter_user_name}</Username>
          <Event>
            <span className="text-lime">{notice_type}</span>
          </Event>
        </>
      )
  }
}

export const Follow = ({ event }: { event: ChannelFollowEvent }) => (
  <>
    <Username>{event.data.payload.user_display_name || event.data.payload.user_name}</Username>
    <Event>Follow</Event>
  </>
)

export const Cheer = ({ event }: { event: CheerEvent }) => (
  <>
    <Username>
      {event.data.payload.is_anonymous
        ? 'Anonymous'
        : event.data.payload.user_display_name || event.data.payload.user_name || 'Unknown'}
    </Username>
    <Event>
      Cheer <span className="text-lime">×{event.data.payload.bits}</span>
    </Event>
  </>
)
