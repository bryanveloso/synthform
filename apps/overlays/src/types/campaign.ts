// Campaign types

export interface Milestone {
  id: string
  threshold: number
  title: string
  description: string
  is_unlocked: boolean
  unlocked_at: string | null
  image_url: string
}

export interface CampaignMetric {
  id: string
  total_subs: number
  total_resubs: number
  total_bits: number
  total_donations: number
  timer_seconds_remaining: number
  timer_started_at: string | null
  timer_paused_at: string | null
  total_duration: number
  stream_started_at: string | null
  extra_data: Record<string, any>
  updated_at: string
}

export interface Campaign {
  id: string
  name: string
  slug: string
  description: string
  start_date: string
  end_date: string
  is_active: boolean

  // Timer configuration
  timer_mode: boolean
  timer_initial_seconds: number
  seconds_per_sub: number
  seconds_per_tier2: number
  seconds_per_tier3: number
  max_timer_seconds: number | null

  // Related data
  metric: CampaignMetric
  milestones: Milestone[]
}

// WebSocket message payloads
export interface CampaignUpdatePayload {
  campaign_id: string
  total_subs: number
  total_resubs: number
  total_bits: number
  timer_seconds_remaining: number
  timer_seconds_added?: number
  extra_data: Record<string, any>
}

export interface MilestoneUnlockedPayload {
  id: string
  threshold: number
  title: string
  description: string
}

export interface TimerUpdatePayload {
  campaign_id: string
  timer_seconds_remaining: number
  timer_started: boolean
  timer_paused?: boolean
}