import type {
  ChatNotificationEvent,
  ChannelFollowEvent,
  CheerEvent,
  ChannelPointsRedemptionEvent,
} from '@/types/events'

export const ChatNotification = ({ event }: { event: ChatNotificationEvent }) => {
  const payload = event.data.payload
  const { notice_type, chatter_display_name, chatter_user_name } = payload

  switch (notice_type) {
    case 'sub':
      return (
        <div>
          <div className="font-caps">New Sub</div>
          <div>{chatter_display_name || chatter_user_name}</div>
        </div>
      )
    case 'resub':
      return (
        <div>
          <div className="font-caps">Resub</div>
          <div>
            {chatter_display_name || chatter_user_name} × {payload.resub?.cumulative_months || '?'}
          </div>
        </div>
      )
    case 'sub_gift':
      return (
        <div>
          <div className="font-caps">Gift</div>
          <div>
            {payload.sub_gift?.recipient?.display_name ||
              payload.sub_gift?.recipient?.name ||
              'Unknown'}
          </div>
        </div>
      )
    case 'community_sub_gift':
      return (
        <div>
          <div className="font-caps">Gift</div>
          <div>
            {chatter_display_name || chatter_user_name} × {payload.community_sub_gift?.total || '?'}
          </div>
        </div>
      )
    case 'raid':
      return (
        <div>
          <div className="font-caps">Raid</div>
          <div>
            {payload.raid?.user?.display_name ||
              payload.raid?.user?.name ||
              chatter_display_name ||
              chatter_user_name}{' '}
            + {payload.raid?.viewer_count || '?'}
          </div>
        </div>
      )
    case 'bits_badge_tier':
      return (
        <div>
          <div className="font-caps">Bits Badge</div>
          <div>
            {chatter_display_name || chatter_user_name} {payload.bits_badge_tier?.tier || ''}
          </div>
        </div>
      )
    case 'charity_donation':
      return (
        <div>
          <div className="font-caps">Charity</div>
          <div>
            {chatter_display_name || chatter_user_name} ${payload.charity_donation?.amount.value || '?'}
          </div>
        </div>
      )
    default:
      return (
        <div>
          <div className="font-caps">{notice_type}</div>
          <div>{chatter_display_name || chatter_user_name}</div>
        </div>
      )
  }
}

export const Follow = ({ event }: { event: ChannelFollowEvent }) => (
  <div>
    <div className="font-caps">Follow</div>
    <div>{event.data.payload.user_display_name || event.data.user_name}</div>
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

