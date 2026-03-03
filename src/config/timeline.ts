/**
 * Timeline Configuration
 *
 * Central configuration for timeline behavior and animations.
 */

// Timing constants
export const TIMELINE_AUTO_HIDE_DELAY = 30000 // 30 seconds before auto-hiding timeline
export const TIMELINE_MAX_EVENTS = 20 // Maximum number of events to display

// Animation durations (in seconds for GSAP)
export const TIMELINE_SHOW_DURATION = 0.5
export const TIMELINE_HIDE_DURATION = 0.3
export const TIMELINE_ITEM_FADE_DURATION = 0.4
export const TIMELINE_ITEM_CASCADE_DELAY = 0.05
export const TIMELINE_NEW_ITEM_DURATION = 1.0
export const TIMELINE_SLIDE_DURATION = 0.5

// Animation positions
export const TIMELINE_HIDDEN_Y = 64 // Pixels to translate when hidden
export const TIMELINE_ITEM_INITIAL_Y = 20 // Initial offset for items

// Alert to timeline orchestration
export const ALERT_PROCESS_DELAY = 50 // Delay to allow alert to process before timeline

// Test event configuration
export const TEST_EVENT_STAGGER_DELAY = 4000 // 4 seconds between test events
