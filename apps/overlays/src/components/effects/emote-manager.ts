// Emote manager singleton for queuing and tracking emotes
type EmoteListener = (emoteId: string) => void

class EmoteManager {
  private static instance: EmoteManager | undefined
  private listeners: Set<EmoteListener> = new Set()

  private constructor() {}

  static getInstance(): EmoteManager {
    if (!EmoteManager.instance) {
      EmoteManager.instance = new EmoteManager()
    }
    return EmoteManager.instance
  }

  on(_event: 'emote', listener: EmoteListener) {
    this.listeners.add(listener)
  }

  off(_event: 'emote', listener: EmoteListener) {
    this.listeners.delete(listener)
  }

  queueEmote(emoteId: string) {
    console.log('[EmoteManager] queueEmote called with:', emoteId)
    // Block global emotes (IDs < 1000000)
    const emoteIdNum = parseInt(emoteId)
    if (!isNaN(emoteIdNum) && emoteIdNum < 1000000) {
      console.log(`[EmoteManager] 🚫 Filtered emote: ${emoteId}`)
      return
    }
    // Just notify immediately
    console.log('[EmoteManager] Notifying listeners for emote:', emoteId)
    this.notifyListeners(emoteId)
  }

  private notifyListeners(emoteId: string) {
    this.listeners.forEach((listener) => {
      try {
        listener(emoteId)
      } catch (error) {
        console.error('Error in emote listener:', error)
      }
    })
  }
}

export const emoteManager = EmoteManager.getInstance()
