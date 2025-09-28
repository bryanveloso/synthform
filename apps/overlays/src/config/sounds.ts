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
  sounds: Record<number, string> // Threshold -> sound file mapping
  defaultSound?: string
}

export const alertSoundConfig: Record<string, SoundConfig> = {
  // Chat notification events
  sub: {
    sounds: {
      1: '/sounds/subscription-1000.ogg', // Tier 1 sub
      2: '/sounds/subscription-2000.ogg', // Tier 2 sub
      3: '/sounds/subscription-3000.ogg', // Tier 3 sub
    },
  },

  resub: {
    sounds: {
      1: '/sounds/resub-1000.ogg', // Tier 1 resub
      2: '/sounds/resub-2000.ogg', // Tier 2 resub
      3: '/sounds/resub-3000.ogg', // Tier 3 resub
    },
  },

  sub_gift: {
    sounds: {
      1: '/sounds/gift.ogg', // Single gift
      // 5: '/sounds/gift-5.mp3',            // 5+ gifts
      // 10: '/sounds/gift-10.mp3',          // 10+ gifts
      // 20: '/sounds/gift-20.mp3',          // 20+ gifts
      // 50: '/sounds/gift-50.mp3',          // 50+ gifts (community gift)
      // 100: '/sounds/gift-mega.mp3',       // 100+ gifts (mega gift)
    },
  },

  community_sub_gift: {
    sounds: {
      1: '/sounds/gift.ogg', // Single gift
      // 5: '/sounds/gift-5.mp3',            // 5+ gifts
      // 10: '/sounds/gift-10.mp3',          // 10+ gifts
      // 20: '/sounds/gift-20.mp3',          // 20+ gifts
      // 50: '/sounds/gift-50.mp3',          // 50+ gifts (community gift)
      // 100: '/sounds/gift-mega.mp3',       // 100+ gifts (mega gift)
    },
  },

  gift_paid_upgrade: {
    sounds: {
      1: '/sounds/subscription-1000.ogg',
      2: '/sounds/subscription-2000.ogg',
      3: '/sounds/subscription-3000.ogg',
    },
  },

  prime_paid_upgrade: {
    sounds: {
      1: '/sounds/subscription-1000.ogg',
      2: '/sounds/subscription-2000.ogg',
      3: '/sounds/subscription-3000.ogg',
    },
  },

  pay_it_forward: {
    sounds: {
      1: '/sounds/gift.ogg',
    },
  },

  bits_badge_tier: {
    sounds: {
      100: '/sounds/cheer-100.ogg', // 100+ bits
      // 500: '/sounds/bits-500.mp3', // 500+ bits
      // 1000: '/sounds/bits-1k.mp3', // 1,000+ bits
      // 5000: '/sounds/bits-5k.mp3', // 5,000+ bits
      // 10000: '/sounds/bits-10k.mp3', // 10,000+ bits
      // 25000: '/sounds/bits-mega.mp3', // 25,000+ bits
    },
  },

  cheer: {
    sounds: {
      100: '/sounds/cheer-100.ogg', // 100+ bits
      // 500: '/sounds/cheer-500.mp3', // 500+ bits
      // 1000: '/sounds/cheer-1k.mp3', // 1,000+ bits
      // 5000: '/sounds/cheer-5k.mp3', // 5,000+ bits
      // 10000: '/sounds/cheer-10k.mp3', // 10,000+ bits
    },
  },

  // Non-chat.notification events
  follow: {
    sounds: {
      1: '/sounds/follow.ogg',
    },
  },

  raid: {
    sounds: {
      1: '/sounds/raid.ogg',
    },
  },

  community_gift_bundle: {
    sounds: {
      1: '/sounds/gift.ogg', // Single gift
      // 5: '/sounds/gift-5.mp3',            // 5+ gifts
      // 10: '/sounds/gift-10.mp3',          // 10+ gifts
      // 20: '/sounds/gift-20.mp3',          // 20+ gifts
      // 50: '/sounds/gift-50.mp3',          // 50+ gifts (community gift)
      // 100: '/sounds/gift-mega.mp3',       // 100+ gifts (mega gift)
    },
  },

  tip: {
    sounds: {
      1: '/sounds/tip.mp3', // Any tip
      5: '/sounds/tip-5.mp3', // $5+ tip
      10: '/sounds/tip-10.mp3', // $10+ tip
      25: '/sounds/tip-25.mp3', // $25+ tip
      50: '/sounds/tip-50.mp3', // $50+ tip
      100: '/sounds/tip-mega.mp3', // $100+ tip
    },
  },
}

/**
 * Find the sound for a given amount based on thresholds
 */
function findSoundByThreshold(sounds: Record<number, string>, amount: number): string | undefined {
  const thresholds = Object.keys(sounds)
    .map(Number)
    .sort((a, b) => b - a)

  for (const threshold of thresholds) {
    if (amount >= threshold) {
      return sounds[threshold]
    }
  }

  return undefined
}

/**
 * Get sound file for an alert based on type and parameters
 */
export function getAlertSound(
  type: string,
  amount?: number,
  tier?: 'Tier 1' | 'Tier 2' | 'Tier 3',
): string | undefined {
  const config = alertSoundConfig[type]
  if (!config) return undefined

  // For tier-based events (sub, resub, upgrades)
  if (tier && (type === 'sub' || type === 'resub' || type.includes('upgrade'))) {
    const tierNum = tier === 'Tier 3' ? 3 : tier === 'Tier 2' ? 2 : 1
    return config.sounds[tierNum] || config.sounds[1]
  }

  // For amount-based events (including community gift bundles)
  if (amount && config.sounds) {
    const sound = findSoundByThreshold(config.sounds, amount)
    if (sound) return sound
  }

  // Return base sound
  return config.sounds[1]
}
