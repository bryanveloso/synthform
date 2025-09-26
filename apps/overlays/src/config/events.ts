/**
 * Event Types
 *
 * All possible event types that can come through the system.
 */

// All possible alert/event types
export const EVENT_TYPES = [
  // Subscriptions
  'subscription',
  'sub',
  'resub',
  'prime_paid_upgrade',
  'gift_paid_upgrade',

  // Gifts
  'gift',
  'sub_gift',
  'community_sub_gift',
  'pay_it_forward',

  // Bits/Cheers
  'cheer',
  'bits_badge_tier',

  // Raids
  'raid',

  // Follows
  'follow',

  // Tips/Donations
  'tip',
  'charity_donation',

  // Announcements
  'announcement',
] as const

export type EventType = typeof EVENT_TYPES[number]