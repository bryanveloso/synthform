import type {
  ChannelFollowEvent,
  ChannelSubscribeEvent,
  SubscriptionGiftEvent,
  SubscriptionMessageEvent,
  CheerEvent,
  ChannelPointsRedemptionEvent,
  ChannelRaidEvent,
  ChatNotificationEvent,
} from '@/types/events'
import type { FC, PropsWithChildren } from 'react'

const Item: FC<PropsWithChildren> = ({ children }) => {
  return <div className="flex items-baseline gap-4 rounded-md p-0.5 px-3 inset-ring-1 inset-ring-shark-800 whitespace-nowrap">{children}</div>
}

export const Follow = ({ event }: { event: ChannelFollowEvent }) => (
  <Item>
    <div>{event.data.payload.user_display_name || event.data.user_name}</div>
    <div className="font-caps text-base whitespace-nowrap text-shark-680">Follow</div>
  </Item>
)

export const Subscription = ({ event }: { event: ChannelSubscribeEvent }) => (
  <Item>
    <div>
      {/* {JSON.stringify(event.data.payload)} */}
      {event.data.payload.user_display_name || event.data.user_name}
    </div>
    <div className="font-caps text-shark-680 text-base whitespace-nowrap">Subscription</div>
  </Item>
)

export const SubscriptionGift = ({ event }: { event: SubscriptionGiftEvent }) => (
  <Item>
    <div>
      {/* {JSON.stringify(event.data.payload)} */}
      {event.data.payload.user_display_name || event.data.user_name} × {event.data.payload.total}
    </div>
    <div className="font-caps text-shark-680 text-base whitespace-nowrap">Gift</div>
  </Item>
)

export const SubscriptionMessage = ({ event }: { event: SubscriptionMessageEvent }) => (
  <Item>
    <div>
      {/* {JSON.stringify(event.data.payload)} */}
      {event.data.payload.user_display_name || event.data.user_name}
    </div>
    <div className="font-caps text-shark-680 text-base whitespace-nowrap">
      {event.data.payload.cumulative_months} Months
    </div>
  </Item>
)

export const Cheer = ({ event }: { event: CheerEvent }) => (
  <Item>
    <div className="font-caps">Cheer</div>
    <div className="font-caps text-shark-680 text-base whitespace-nowrap">
      {event.data.payload.is_anonymous
        ? 'Anonymous'
        : event.data.payload.user_display_name || event.data.payload.user_name || 'Unknown'}{' '}
      × {event.data.payload.bits}
    </div>
  </Item>
)

const OOF_ID = '5685d03e-80c2-4640-ba06-566fb8bbc4ce'
const SIP_ID = 'cdee531b-d614-4f02-b4a0-7f5c5d9f321c'

export const RedemptionAdd = ({ event }: { event: ChannelPointsRedemptionEvent }) => (
  <Item>
    {event.data.payload.reward.id === OOF_ID && (
      <img src="/images/emotes/oof.png" alt="OOF" className="w-8" />
    )}
  </Item>
)
  
export const Raid = ({ event }: { event: ChannelRaidEvent }) => (
  <Item>
    <div>
      {event.data.payload.from_broadcaster_user_display_name} + {event.data.payload.viewers}
    </div>
    <div className="font-caps text-shark-680 text-base whitespace-nowrap">Raid</div>
  </Item>
)

// Mega component for handling all chat notification events
export const ChatNotification = ({ event }: { event: ChatNotificationEvent }) => {
  const payload = event.data.payload
  const { notice_type, chatter_display_name, chatter_user_name } = payload

  switch (notice_type) {
    case 'sub':
      return (
        <Item>
          <div>{chatter_display_name || chatter_user_name}</div>
          <div className="font-caps text-shark-680 text-base whitespace-nowrap">New Sub</div>
        </Item>
      )

    case 'resub':
      return (
        <Item>
          <div>{chatter_display_name || chatter_user_name}</div>
          <div className="font-caps text-shark-680 text-base whitespace-nowrap">
            {payload.resub?.cumulative_months || '?'} Months
          </div>
        </Item>
      )

    case 'sub_gift':
      return (
        <Item>
          <div>{payload.sub_gift?.recipient_user_name || 'Someone'}</div>
          <div className="font-caps text-shark-680 text-base whitespace-nowrap">Gift Sub</div>
        </Item>
      )

    case 'community_sub_gift':
      return (
        <Item>
          <div>
            {chatter_display_name || chatter_user_name} × {payload.community_sub_gift?.total || '?'}
          </div>
          <div className="font-caps text-shark-680 text-base whitespace-nowrap">Gift</div>
        </Item>
      )

    case 'raid':
      return (
        <Item>
          <div>
            {payload.raid?.user_name || chatter_display_name || chatter_user_name} + {payload.raid?.viewer_count || '?'}
          </div>
          <div className="font-caps text-shark-680 text-base whitespace-nowrap">Raid</div>
        </Item>
      )

    case 'bits_badge_tier':
      return (
        <Item>
          <div>{chatter_display_name || chatter_user_name}</div>
          <div className="font-caps text-shark-680 text-base whitespace-nowrap">
            Bits Badge {payload.bits_badge_tier?.tier || ''}
          </div>
        </Item>
      )

    case 'charity_donation':
      return (
        <Item>
          <div>{chatter_display_name || chatter_user_name}</div>
          <div className="font-caps text-shark-680 text-base whitespace-nowrap">
            ${payload.charity_donation?.amount.value || '?'} Charity
          </div>
        </Item>
      )

    default:
      // Fallback for unknown notice types
      return (
        <Item>
          <div>{chatter_display_name || chatter_user_name}</div>
          <div className="font-caps text-shark-680 text-base whitespace-nowrap">{notice_type}</div>
        </Item>
      )
  }
}
