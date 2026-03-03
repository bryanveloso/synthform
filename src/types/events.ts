// Base event structure from WebSocket
export interface WebSocketMessage<T = unknown> {
  type: string
  payload: T
  timestamp: string
  sequence: number
}

// Base event structure for timeline events
export interface BaseEvent<T = Record<string, unknown>> {
  id: string
  type: string
  data: {
    timestamp: string
    payload: T
    user_name?: string
  }
}

// User-related fields common to many events
interface UserFields {
  user_id: string
  user_name: string
  user_display_name: string
}

interface BroadcasterFields {
  broadcaster_user_id: string
  broadcaster_user_name: string
  broadcaster_user_display_name: string
}

// Channel Follow Event
export interface FollowPayload extends UserFields, BroadcasterFields {
  followed_at: string
}

export interface ChannelFollowEvent extends BaseEvent<FollowPayload> {
  type: 'twitch.channel.follow'
  data: {
    timestamp: string
    payload: FollowPayload
    user_name: string
  }
}

// Channel Subscribe Event
export interface SubscribePayload extends UserFields, BroadcasterFields {
  tier: string
  is_gift: boolean
}

export interface ChannelSubscribeEvent extends BaseEvent<SubscribePayload> {
  type: 'twitch.channel.subscribe'
  data: {
    timestamp: string
    payload: SubscribePayload
    user_name: string
  }
}

// Channel Subscription Gift Event
export interface SubscriptionGiftPayload extends UserFields, BroadcasterFields {
  total: number
  tier: string
  cumulative_total: number | null
  is_anonymous: boolean
}

export interface SubscriptionGiftEvent extends BaseEvent<SubscriptionGiftPayload> {
  type: 'twitch.channel.subscription.gift'
  data: {
    timestamp: string
    payload: SubscriptionGiftPayload
    user_name: string
  }
}

// Channel Subscription Message Event
export interface SubscriptionMessagePayload extends UserFields, BroadcasterFields {
  tier: string
  message: string
  cumulative_months: number
  streak_months: number | null
  duration_months: number
  emotes: Array<{
    id: string
    name: string
    positions: Array<{
      start: number
      end: number
    }>
  }> | null
}

export interface SubscriptionMessageEvent extends BaseEvent<SubscriptionMessagePayload> {
  type: 'twitch.channel.subscription.message'
  data: {
    timestamp: string
    payload: SubscriptionMessagePayload
    user_name: string
  }
}

// Channel Cheer Event
export interface CheerPayload extends BroadcasterFields {
  bits: number
  message: string
  is_anonymous: boolean
  user_id?: string | null
  user_name?: string | null
  user_display_name?: string | null
}

export interface CheerEvent extends BaseEvent<CheerPayload> {
  type: 'twitch.channel.cheer'
  data: {
    timestamp: string
    payload: CheerPayload
    user_name?: string
  }
}

// Channel Points Custom Reward Redemption Event
export interface RewardInfo {
  id: string
  title: string
  cost: number
  prompt: string
}

export interface ChannelPointsRedemptionPayload extends UserFields, BroadcasterFields {
  id: string
  user_input: string | null
  status: string
  reward: RewardInfo
  redeemed_at: string
}

export interface ChannelPointsRedemptionEvent extends BaseEvent<ChannelPointsRedemptionPayload> {
  type: 'twitch.channel.channel_points_custom_reward_redemption.add'
  data: {
    timestamp: string
    payload: ChannelPointsRedemptionPayload
    user_name: string
  }
}

// Channel Raid Event
export interface ChannelRaidPayload {
  from_broadcaster_user_id: string
  from_broadcaster_user_name: string
  from_broadcaster_user_display_name: string
  to_broadcaster_user_id: string
  to_broadcaster_user_name: string
  to_broadcaster_user_display_name: string
  viewers: number
}

export interface ChannelRaidEvent extends BaseEvent<ChannelRaidPayload> {
  type: 'twitch.channel.raid'
  data: {
    timestamp: string
    payload: ChannelRaidPayload
    user_name: string // Will be from_broadcaster_user_name
  }
}

// Chat Notification Event (consolidated events from Twitch)
export interface ChatNotificationPayload {
  broadcaster_user_id: string
  broadcaster_user_name: string
  chatter_user_id: string
  chatter_user_name: string
  chatter_display_name: string
  chatter_is_anonymous: boolean
  colour: string
  badges: Array<{
    set_id: string
    id: string
    info: string
  }>
  system_message: string
  message_id: string
  message: {
    text: string
    fragments: Array<{
      type: string
      text: string
      emote?: {
        id: string | null
        set_id: string | null
      } | null
    }>
  }
  notice_type:
    | 'sub'
    | 'resub'
    | 'sub_gift'
    | 'community_sub_gift'
    | 'gift_paid_upgrade'
    | 'prime_paid_upgrade'
    | 'pay_it_forward'
    | 'raid'
    | 'unraid'
    | 'announcement'
    | 'bits_badge_tier'
    | 'charity_donation'
    | 'shared_chat_sub'
    | 'shared_chat_resub'
    | 'shared_chat_sub_gift'
    | 'shared_chat_community_sub_gift'
    | 'shared_chat_gift_paid_upgrade'
    | 'shared_chat_prime_paid_upgrade'
    | 'shared_chat_raid'
    | 'shared_chat_pay_it_forward'
    | 'shared_chat_announcement'
    | string // Allow other notice types we might not know about
  // Type-specific data fields (only one will be populated based on notice_type)
  // These match TwitchIO's actual field names after serialization
  sub?: {
    tier: string  // "1000", "2000", or "3000"
    prime: boolean
    months: number
  }
  resub?: {
    tier: string  // "1000", "2000", or "3000"
    prime: boolean
    gift: boolean
    months: number
    cumulative_months: number
    streak_months: number | null
    anonymous?: boolean | null
    gifter?: {  // PartialUser object
      id: string
      name: string
      display_name: string
      login: string
    } | null
  }
  sub_gift?: {
    tier: string  // "1000", "2000", or "3000"
    months: number
    cumulative_total: number | null
    community_gift_id: string | null
    recipient: {  // PartialUser object
      id: string
      name: string
      display_name: string
      login: string
    }
  }
  community_sub_gift?: {
    tier: string  // "1000", "2000", or "3000"
    total: number
    cumulative_total: number | null
    id: string
  }
  gift_paid_upgrade?: {
    anonymous: boolean
    gifter?: {  // PartialUser object
      id: string
      name: string
      display_name: string
      login: string
    } | null
  }
  prime_paid_upgrade?: {
    tier: string  // "1000", "2000", or "3000"
  }
  raid?: {
    user: {  // PartialUser object
      id: string
      name: string
      display_name: string
      login: string
    }
    viewer_count: number
    profile_image: {  // Asset object
      url: string
    }
  }
  unraid?: null  // Always null
  pay_it_forward?: {
    anonymous: boolean
    gifter?: {  // PartialUser object
      id: string
      name: string
      display_name: string
      login: string
    } | null
  }
  announcement?: {
    colour: string  // TwitchIO uses British spelling
  }
  bits_badge_tier?: {
    tier: number
  }
  charity_donation?: {
    name: string
    amount: {  // CharityValues object
      value: number
      decimal_places: number
      currency: string
    }
  }
  // Shared chat variants (same structure as their non-shared counterparts)
  shared_sub?: {
    tier: string
    prime: boolean
    months: number
  }
  shared_resub?: {
    tier: string
    prime: boolean
    gift: boolean
    months: number
    cumulative_months: number
    streak_months: number | null
    anonymous?: boolean | null
    gifter?: {
      id: string
      name: string
      display_name: string
      login: string
    } | null
  }
  shared_sub_gift?: {
    tier: string
    months: number
    cumulative_total: number | null
    community_gift_id: string | null
    recipient: {
      id: string
      name: string
      display_name: string
      login: string
    }
  }
  shared_community_sub_gift?: {
    tier: string
    total: number
    cumulative_total: number | null
    id: string
  }
  shared_gift_paid_upgrade?: {
    anonymous: boolean
    gifter?: {
      id: string
      name: string
      display_name: string
      login: string
    } | null
  }
  shared_prime_paid_upgrade?: {
    tier: string
  }
  shared_raid?: {
    user: {
      id: string
      name: string
      display_name: string
      login: string
    }
    viewer_count: number
    profile_image: {
      url: string
    }
  }
  shared_pay_it_forward?: {
    anonymous: boolean
    gifter?: {
      id: string
      name: string
      display_name: string
      login: string
    } | null
  }
  shared_announcement?: {
    colour: string
  }
}

export interface ChatNotificationEvent extends BaseEvent<ChatNotificationPayload> {
  type: 'twitch.channel.chat.notification'
  data: {
    timestamp: string
    payload: ChatNotificationPayload
    user_name: string
  }
}

// Community Gift Bundle Event (aggregated gift subs)
export interface CommunityGiftBundlePayload {
  gifter: string
  total: number
  tier?: string
}

export interface CommunityGiftBundleEvent extends BaseEvent<CommunityGiftBundlePayload> {
  type: 'twitch.channel.subscription.gift.bundle'
  data: {
    timestamp: string
    payload: CommunityGiftBundlePayload
    user_name: string
  }
}

// Union type for all timeline events
export type TimelineEvent =
  | ChannelFollowEvent
  | ChannelSubscribeEvent
  | SubscriptionGiftEvent
  | SubscriptionMessageEvent
  | CheerEvent
  | ChannelPointsRedemptionEvent
  | ChannelRaidEvent
  | ChatNotificationEvent
  | CommunityGiftBundleEvent

// Type guard functions
export function isFollowEvent(event: TimelineEvent): event is ChannelFollowEvent {
  return event.type === 'twitch.channel.follow'
}

export function isSubscribeEvent(event: TimelineEvent): event is ChannelSubscribeEvent {
  return event.type === 'twitch.channel.subscribe'
}

export function isSubscriptionGiftEvent(event: TimelineEvent): event is SubscriptionGiftEvent {
  return event.type === 'twitch.channel.subscription.gift'
}

export function isSubscriptionMessageEvent(event: TimelineEvent): event is SubscriptionMessageEvent {
  return event.type === 'twitch.channel.subscription.message'
}

export function isCheerEvent(event: TimelineEvent): event is CheerEvent {
  return event.type === 'twitch.channel.cheer'
}

export function isPointsRedemptionEvent(event: TimelineEvent): event is ChannelPointsRedemptionEvent {
  return event.type === 'twitch.channel.channel_points_custom_reward_redemption.add'
}

export function isRaidEvent(event: TimelineEvent): event is ChannelRaidEvent {
  return event.type === 'twitch.channel.raid'
}

export function isChatNotificationEvent(event: TimelineEvent): event is ChatNotificationEvent {
  return event.type === 'twitch.channel.chat.notification'
}
