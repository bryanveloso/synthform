/**
 * Test Event Fixtures
 *
 * These are properly structured test events that match EXACTLY what the server sends.
 * Use these for all testing to ensure consistency.
 */

import type {
  TimelineEvent,
  ChatNotificationEvent,
  ChannelFollowEvent,
  CheerEvent,
} from '@/types/events'
import type { AlertData } from '@/types/server'

interface TestEventPair {
  alert: AlertData
  timeline: TimelineEvent
}

export class TestEventFactory {
  private static generateId(): string {
    return `test-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  private static getRandomUsername(): string {
    const usernames = [
      'TestViewer123',
      'StreamerFan42',
      'CoolUser99',
      'AwesomeSupporter',
      'TwitchWatcher2024',
      'GameEnthusiast',
      'ChatChampion',
      'SubSquadLeader',
    ]
    return usernames[Math.floor(Math.random() * usernames.length)]
  }

  static follow(username?: string): TestEventPair {
    const eventId = this.generateId()
    const user = username || this.getRandomUsername()
    const timestamp = new Date().toISOString()

    const alert: AlertData = {
      id: eventId,
      type: 'twitch.channel.follow',
      message: `${user} just followed!`,
      user_name: user,
      timestamp,
    }

    const timeline: ChannelFollowEvent = {
      id: eventId,
      type: 'twitch.channel.follow',
      data: {
        timestamp,
        user_name: user,
        payload: {
          user_id: `user-${eventId}`,
          user_name: user,
          user_display_name: user,
          broadcaster_user_id: 'broadcaster-123',
          broadcaster_user_name: 'broadcaster',
          broadcaster_user_display_name: 'Broadcaster',
          followed_at: timestamp,
        },
      },
    }

    return { alert, timeline }
  }

  static sub(username?: string, tier: 'Tier 1' | 'Tier 2' | 'Tier 3' = 'Tier 1'): TestEventPair {
    const eventId = this.generateId()
    const user = username || this.getRandomUsername()
    const timestamp = new Date().toISOString()

    const alert: AlertData = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      message: `${user} subscribed at ${tier}!`,
      user_name: user,
      timestamp,
      tier,
      data: {
        payload: {
          notice_type: 'sub',
          sub_tier: tier === 'Tier 3' ? '3000' : tier === 'Tier 2' ? '2000' : '1000',
        },
      },
    }

    const timeline: ChatNotificationEvent = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      data: {
        timestamp,
        user_name: user,
        payload: {
          broadcaster_user_id: 'broadcaster-123',
          broadcaster_user_name: 'broadcaster',
          chatter_user_id: `user-${eventId}`,
          chatter_user_name: user,
          chatter_display_name: user,
          chatter_is_anonymous: false,
          colour: '#9147FF',
          badges: [],
          system_message: `${user} subscribed at ${tier}!`,
          message_id: `msg-${eventId}`,
          message: {
            text: '',
            fragments: [],
          },
          notice_type: 'sub',
          sub: {
            tier: tier === 'Tier 1' ? '1000' : tier === 'Tier 2' ? '2000' : '3000',
            prime: false,
            months: 1,
          },
        },
      },
    }

    return { alert, timeline }
  }

  static resub(
    username?: string,
    months: number = 12,
    tier: 'Tier 1' | 'Tier 2' | 'Tier 3' = 'Tier 1',
  ): TestEventPair {
    const eventId = this.generateId()
    const user = username || this.getRandomUsername()
    const timestamp = new Date().toISOString()

    const alert: AlertData = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      message: `${user} resubscribed for ${months} months at ${tier}!`,
      user_name: user,
      timestamp,
      tier,
      months,
      data: {
        payload: {
          notice_type: 'resub',
          sub_tier: tier === 'Tier 3' ? '3000' : tier === 'Tier 2' ? '2000' : '1000',
          cumulative_months: months,
        },
      },
    }

    const timeline: ChatNotificationEvent = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      data: {
        timestamp,
        user_name: user,
        payload: {
          broadcaster_user_id: 'broadcaster-123',
          broadcaster_user_name: 'broadcaster',
          chatter_user_id: `user-${eventId}`,
          chatter_user_name: user,
          chatter_display_name: user,
          chatter_is_anonymous: false,
          colour: '#9147FF',
          badges: [],
          system_message: `${user} subscribed for ${months} months!`,
          message_id: `msg-${eventId}`,
          message: {
            text: `Thanks for ${months} months of support!`,
            fragments: [
              {
                type: 'text',
                text: `Thanks for ${months} months of support!`,
              },
            ],
          },
          notice_type: 'resub',
          resub: {
            tier: tier === 'Tier 1' ? '1000' : tier === 'Tier 2' ? '2000' : '3000',
            prime: false,
            gift: false,
            months: 1,
            cumulative_months: months,
            streak_months: Math.max(1, months - 2),
          },
        },
      },
    }

    return { alert, timeline }
  }

  static cheer(username?: string, bits: number = 500): TestEventPair {
    const eventId = this.generateId()
    const user = username || this.getRandomUsername()
    const timestamp = new Date().toISOString()

    const alert: AlertData = {
      id: eventId,
      type: 'twitch.channel.cheer',
      message: `${user} cheered ${bits} bits!`,
      user_name: user,
      timestamp,
      amount: bits,
    }

    const timeline: CheerEvent = {
      id: eventId,
      type: 'twitch.channel.cheer',
      data: {
        timestamp,
        user_name: user,
        payload: {
          broadcaster_user_id: 'broadcaster-123',
          broadcaster_user_name: 'broadcaster',
          broadcaster_user_display_name: 'Broadcaster',
          bits,
          message: `Cheering ${bits} bits!`,
          is_anonymous: false,
          user_id: `user-${eventId}`,
          user_name: user,
          user_display_name: user,
        },
      },
    }

    return { alert, timeline }
  }

  static raid(username?: string, viewers: number = 25): TestEventPair {
    const eventId = this.generateId()
    const user = username || this.getRandomUsername()
    const timestamp = new Date().toISOString()

    const alert: AlertData = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      message: `${user} raided with ${viewers} viewers!`,
      user_name: user,
      timestamp,
      amount: viewers,
      data: {
        payload: {
          notice_type: 'raid',
          viewer_count: viewers,
        },
      },
    }

    const timeline: ChatNotificationEvent = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      data: {
        timestamp,
        user_name: user,
        payload: {
          broadcaster_user_id: 'broadcaster-123',
          broadcaster_user_name: 'broadcaster',
          chatter_user_id: `user-${eventId}`,
          chatter_user_name: user,
          chatter_display_name: user,
          chatter_is_anonymous: false,
          colour: '#9147FF',
          badges: [],
          system_message: `${user} is raiding with a party of ${viewers}!`,
          message_id: `msg-${eventId}`,
          message: {
            text: '',
            fragments: [],
          },
          notice_type: 'raid',
          raid: {
            user: {
              id: `user-${eventId}`,
              name: user,
              display_name: user,
              login: user.toLowerCase(),
            },
            viewer_count: viewers,
            profile_image: {
              url: 'https://static-cdn.jtvnw.net/user-default-pictures-uv/13e5fa74-defa-11e9-809c-784f43822e80-profile_image-70x70.png',
            },
          },
        },
      },
    }

    return { alert, timeline }
  }

  static subGift(
    username?: string,
    recipient: string = 'RecipientUser',
    tier: 'Tier 1' | 'Tier 2' | 'Tier 3' = 'Tier 1',
  ): TestEventPair {
    const eventId = this.generateId()
    const user = username || this.getRandomUsername()
    const timestamp = new Date().toISOString()

    const alert: AlertData = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      message: `${user} gifted a sub to ${recipient}!`,
      user_name: user,
      timestamp,
      amount: 1,
      tier,
      data: {
        payload: {
          notice_type: 'sub_gift',
          sub_tier: tier === 'Tier 3' ? '3000' : tier === 'Tier 2' ? '2000' : '1000',
        },
      },
    }

    const timeline: ChatNotificationEvent = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      data: {
        timestamp,
        user_name: user,
        payload: {
          broadcaster_user_id: 'broadcaster-123',
          broadcaster_user_name: 'broadcaster',
          chatter_user_id: `user-${eventId}`,
          chatter_user_name: user,
          chatter_display_name: user,
          chatter_is_anonymous: false,
          colour: '#9147FF',
          badges: [],
          system_message: `${user} gifted a sub to ${recipient}!`,
          message_id: `msg-${eventId}`,
          message: {
            text: '',
            fragments: [],
          },
          notice_type: 'sub_gift',
          sub_gift: {
            tier: tier === 'Tier 1' ? '1000' : tier === 'Tier 2' ? '2000' : '3000',
            months: 1,
            cumulative_total: null,
            community_gift_id: null,
            recipient: {
              id: 'recipient-123',
              name: recipient.toLowerCase(),
              display_name: recipient,
              login: recipient.toLowerCase(),
            },
          },
        },
      },
    }

    return { alert, timeline }
  }

  static communityGift(
    username?: string,
    count: number = 5,
    tier: 'Tier 1' | 'Tier 2' | 'Tier 3' = 'Tier 1',
  ): TestEventPair {
    const eventId = this.generateId()
    const user = username || this.getRandomUsername()
    const timestamp = new Date().toISOString()

    const alert: AlertData = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      message: `${user} gifted ${count} subs to the community!`,
      user_name: user,
      timestamp,
      amount: count,
      tier,
      data: {
        payload: {
          notice_type: 'community_sub_gift',
          sub_tier: tier === 'Tier 3' ? '3000' : tier === 'Tier 2' ? '2000' : '1000',
          total: count,
        },
      },
    }

    const timeline: ChatNotificationEvent = {
      id: eventId,
      type: 'twitch.channel.chat.notification',
      data: {
        timestamp,
        user_name: user,
        payload: {
          broadcaster_user_id: 'broadcaster-123',
          broadcaster_user_name: 'broadcaster',
          chatter_user_id: `user-${eventId}`,
          chatter_user_name: user,
          chatter_display_name: user,
          chatter_is_anonymous: false,
          colour: '#9147FF',
          badges: [],
          system_message: `${user} is gifting ${count} Tier ${tier.split(' ')[1]} Subs to the community!`,
          message_id: `msg-${eventId}`,
          message: {
            text: '',
            fragments: [],
          },
          notice_type: 'community_sub_gift',
          community_sub_gift: {
            tier: tier === 'Tier 1' ? '1000' : tier === 'Tier 2' ? '2000' : '3000',
            total: count,
            cumulative_total: count * 5,
            id: `community-${eventId}`,
          },
        },
      },
    }

    return { alert, timeline }
  }

  // Generate a random event
  static random(): TestEventPair {
    const types = ['follow', 'sub', 'resub', 'cheer', 'raid', 'subGift', 'communityGift']
    const type = types[Math.floor(Math.random() * types.length)]

    switch (type) {
      case 'follow':
        return this.follow()
      case 'sub':
        return this.sub()
      case 'resub':
        return this.resub(undefined, Math.floor(Math.random() * 24) + 1)
      case 'cheer':
        return this.cheer(undefined, Math.floor(Math.random() * 1000) + 100)
      case 'raid':
        return this.raid(undefined, Math.floor(Math.random() * 50) + 5)
      case 'subGift':
        return this.subGift()
      case 'communityGift':
        return this.communityGift(undefined, Math.floor(Math.random() * 10) + 1)
      default:
        return this.follow()
    }
  }
}

// Export some pre-made test events for quick testing
export const TEST_EVENTS = {
  follow: TestEventFactory.follow('TestFollower'),
  sub: TestEventFactory.sub('TestSubscriber', 'Tier 1'),
  resub: TestEventFactory.resub('LoyalViewer', 24, 'Tier 2'),
  cheer: TestEventFactory.cheer('BitsCheerer', 1000),
  raid: TestEventFactory.raid('RaidLeader', 50),
  subGift: TestEventFactory.subGift('Gifter', 'LuckyRecipient', 'Tier 1'),
  communityGift: TestEventFactory.communityGift('GenerousGifter', 10, 'Tier 1'),
}
