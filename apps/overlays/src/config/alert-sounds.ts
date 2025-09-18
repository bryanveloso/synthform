/**
 * Alert Sound Configuration
 *
 * Maps event types to sound files based on magnitude thresholds.
 * Higher thresholds should have more epic/exciting sounds.
 *
 * Sound files should be placed in /public/sounds/ directory.
 *
 * Thresholds are checked in descending order - the first match is used.
 * For example, a 15-month resub would use the 12-month sound.
 */

export interface SoundConfig {
  tiers?: Record<number, number> // Tier multipliers for subscriptions
  sounds: Record<number, string> // Threshold -> sound file mapping
  defaultSound?: string
}

export const alertSoundConfig: Record<string, SoundConfig> = {
  subscription: {
    // Different sounds per tier (no multiplication, just tier-based)
    sounds: {
      1: '/sounds/sub.mp3',              // Tier 1 sub
      2: '/sounds/sub-t2.mp3',           // Tier 2 sub
      3: '/sounds/sub-t3.mp3',           // Tier 3 sub
    },
  },

  resub: {
    // Different sounds per tier for resubs too
    sounds: {
      1: '/sounds/resub.mp3',            // Tier 1 resub
      2: '/sounds/resub-t2.mp3',         // Tier 2 resub
      3: '/sounds/resub-t3.mp3',         // Tier 3 resub
    },
  },

  gift: {
    sounds: {
      1: '/sounds/gift.mp3',             // Single gift
      5: '/sounds/gift-5.mp3',           // 5+ gifts
      10: '/sounds/gift-10.mp3',         // 10+ gifts
      20: '/sounds/gift-20.mp3',         // 20+ gifts
      50: '/sounds/gift-50.mp3',         // 50+ gifts (community gift)
      100: '/sounds/gift-mega.mp3',      // 100+ gifts (mega gift)
    },
  },

  cheer: {
    sounds: {
      100: '/sounds/bits.mp3',           // 100+ bits
      500: '/sounds/bits-500.mp3',       // 500+ bits
      1000: '/sounds/bits-1k.mp3',       // 1,000+ bits
      5000: '/sounds/bits-5k.mp3',       // 5,000+ bits
      10000: '/sounds/bits-10k.mp3',     // 10,000+ bits
      25000: '/sounds/bits-mega.mp3',    // 25,000+ bits
    },
  },

  tip: {
    sounds: {
      1: '/sounds/tip.mp3',              // Any tip
      5: '/sounds/tip-5.mp3',            // $5+ tip
      10: '/sounds/tip-10.mp3',          // $10+ tip
      25: '/sounds/tip-25.mp3',          // $25+ tip
      50: '/sounds/tip-50.mp3',          // $50+ tip
      100: '/sounds/tip-mega.mp3',       // $100+ tip
    },
  },

  follow: {
    sounds: {
      1: '/sounds/follow.mp3',           // All follows use same sound
    },
  },

  raid: {
    sounds: {
      1: '/sounds/raid.mp3',             // All raids use same sound
    },
  },
}

/**
 * Helper function to get sound file for an alert
 *
 * @param type - Alert type
 * @param amount - Amount (for gifts, cheers, tips)
 * @param tier - Subscription tier
 * @returns Path to sound file or undefined
 */
export function getAlertSound(
  type: string,
  amount?: number,
  tier?: 'Tier 1' | 'Tier 2' | 'Tier 3'
): string | undefined {
  const config = alertSoundConfig[type]
  if (!config) return undefined

  // For subscriptions/resubs, use tier-specific sounds
  if (type === 'subscription' || type === 'resub') {
    const tierNum = tier === 'Tier 3' ? 3 : tier === 'Tier 2' ? 2 : 1
    return config.sounds[tierNum] || config.sounds[1]
  }

  // For amount-based events
  if (amount && config.sounds) {
    const thresholds = Object.keys(config.sounds)
      .map(Number)
      .sort((a, b) => b - a)

    for (const threshold of thresholds) {
      if (amount >= threshold) {
        return config.sounds[threshold]
      }
    }
  }

  // Return base sound
  return config.sounds[1]
}
