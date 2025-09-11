import type {
  ChannelFollowEvent,
  ChannelSubscribeEvent,
  SubscriptionGiftEvent,
  SubscriptionMessageEvent,
  CheerEvent,
  ChannelPointsRedemptionEvent,
  ChannelRaidEvent,
} from '@/types/events'

export const Follow = ({ event }: { event: ChannelFollowEvent }) => (
  <div>
    <div className="font-caps">Follow</div>
    <div>{event.data.payload.user_display_name || event.data.user_name}</div>
  </div>
)

export const Subscription = ({ event }: { event: ChannelSubscribeEvent }) => (
  <div>
    <div className="font-caps">Subscription</div>
    <div>
      {/* {JSON.stringify(event.data.payload)} */}
      {event.data.payload.user_display_name || event.data.user_name}
    </div>
  </div>
)

export const SubscriptionGift = ({ event }: { event: SubscriptionGiftEvent }) => (
  <div>
    <div className="font-caps">Gift</div>
    <div>
      {/* {JSON.stringify(event.data.payload)} */}
      {event.data.payload.user_display_name || event.data.user_name} × {event.data.payload.total}
    </div>
  </div>
)

export const SubscriptionMessage = ({ event }: { event: SubscriptionMessageEvent }) => (
  <div>
    <div className="font-caps">Resub</div>
    <div>
      {/* {JSON.stringify(event.data.payload)} */}
      {event.data.payload.user_display_name || event.data.user_name} × {event.data.payload.cumulative_months}
    </div>
  </div>
)

export const Cheer = ({ event }: { event: CheerEvent }) => (
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

const OOF_ID = '5685d03e-80c2-4640-ba06-566fb8bbc4ce'
const SIP_ID = 'cdee531b-d614-4f02-b4a0-7f5c5d9f321c'

export const RedemptionAdd = ({ event }: { event: ChannelPointsRedemptionEvent }) => (
  <div>
    {event.data.payload.reward.id === OOF_ID && (
      <img src="/images/emotes/oof.png" alt="OOF" className="w-8" />
    )}
  </div>
)

export const Raid = ({ event }: { event: ChannelRaidEvent }) => (
  <div>
    <div className="font-caps">Raid</div>
    <div>
      {event.data.payload.from_broadcaster_user_display_name} × {event.data.payload.viewers}
    </div>
  </div>
)
