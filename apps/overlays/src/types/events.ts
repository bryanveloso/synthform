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
  color: string
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
  notice_type: string
  // Type-specific data fields (only one will be populated based on notice_type)
  sub?: {
    sub_tier: string
    is_prime: boolean
    duration_months: number
  }
  resub?: {
    cumulative_months: number
    duration_months: number
    streak_months: number | null
    sub_tier: string
    is_prime: boolean
    is_gift: boolean
    gifter_is_anonymous?: boolean | null
    gifter_user_id?: string | null
    gifter_user_name?: string | null
    gifter_user_login?: string | null
  }
  sub_gift?: {
    duration_months: number
    cumulative_total: number | null
    recipient_user_id: string
    recipient_user_name: string
    recipient_user_login: string
    sub_tier: string
    community_gift_id?: string | null
  }
  community_sub_gift?: {
    id: string
    total: number
    sub_tier: string
    cumulative_total: number | null
  }
  gift_paid_upgrade?: {
    is_anonymous: boolean
    gifter_user_id?: string | null
    gifter_user_name?: string | null
    gifter_user_login?: string | null
  }
  prime_paid_upgrade?: {
    sub_tier: string
  }
  raid?: {
    user_id: string
    user_name: string
    user_login: string
    viewer_count: number
    profile_image_url: string
  }
  unraid?: Record<string, never>
  pay_it_forward?: {
    is_anonymous: boolean
    gifter_user_id?: string | null
    gifter_user_name?: string | null
    gifter_user_login?: string | null
  }
  announcement?: {
    color: string
  }
  bits_badge_tier?: {
    tier: number
  }
  charity_donation?: {
    charity_name: string
    amount: {
      value: number
      decimal_places: number
      currency: string
    }
  }
}

export interface ChatNotificationEvent extends BaseEvent<ChatNotificationPayload> {
  type: string // Dynamic based on notice_type mapping
  data: {
    timestamp: string
    payload: ChatNotificationPayload
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
