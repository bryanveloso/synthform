import type {
  ChannelFollowEvent,
  ChannelSubscribeEvent,
  SubscriptionGiftEvent,
  SubscriptionMessageEvent,
  CheerEvent,
  ChannelPointsRedemptionEvent,
  ChannelRaidEvent,
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
