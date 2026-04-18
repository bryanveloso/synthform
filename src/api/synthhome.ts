const SYNTHHOME_URL = import.meta.env.VITE_SYNTHHOME_URL || 'http://saya:7175'

// ---------------------------------------------------------------------------
// WebSocket: Real-time weather data via Synthhome
// ---------------------------------------------------------------------------

export interface SynthhomeMessage {
  type: string
  source: string
  timestamp: string
  data: Record<string, unknown>
}

export interface WeatherObservation {
  timestamp: string
  readings: Record<string, number>
}

export interface WeatherRapidWind {
  timestamp: string
  windSpeedMph: number
  windDir: number
}

export interface WeatherLightningStrike {
  timestamp: string
  distanceMi: number
  energy: number
}

export interface WeatherConnectionOptions {
  onObservation: (obs: WeatherObservation) => void
  onRapidWind: (wind: WeatherRapidWind) => void
  onLightningStrike: (strike: WeatherLightningStrike) => void
  onRainStart: () => void
  onConnected: () => void
  onDisconnected: () => void
  onError: (error: string) => void
}

export function connectWeather(options: WeatherConnectionOptions): () => void {
  const wsUrl = SYNTHHOME_URL.replace(/^http/, 'ws')
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let destroyed = false

  function connect() {
    if (destroyed) return

    ws = new WebSocket(`${wsUrl}/ws/tempest/`)

    ws.onopen = () => {
      options.onConnected()
    }

    ws.onmessage = (event) => {
      try {
        const msg: SynthhomeMessage = JSON.parse(event.data)

        switch (msg.type) {
          case 'observation':
            options.onObservation({
              timestamp: msg.data.timestamp as string,
              readings: msg.data.readings as Record<string, number>,
            })
            break
          case 'rapid_wind':
            options.onRapidWind({
              timestamp: msg.data.timestamp as string,
              windSpeedMph: msg.data.wind_speed_mph as number,
              windDir: msg.data.wind_dir as number,
            })
            break
          case 'lightning_strike':
            options.onLightningStrike({
              timestamp: msg.data.timestamp as string,
              distanceMi: msg.data.distance_mi as number,
              energy: msg.data.energy as number,
            })
            break
          case 'rain_start':
            options.onRainStart()
            break
        }
      } catch {
        // Ignore parse errors
      }
    }

    ws.onclose = () => {
      options.onDisconnected()
      if (!destroyed) {
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    ws.onerror = () => {
      options.onError('Synthhome weather WebSocket error')
    }
  }

  connect()

  return () => {
    destroyed = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  }
}

// ---------------------------------------------------------------------------
// REST: Forecast and history from Synthhome API
// ---------------------------------------------------------------------------

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${SYNTHHOME_URL}/api${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export interface SynthhomeForecastDay {
  day_start_local: number
  conditions: string
  icon: string
  air_temp_high: number
  air_temp_low: number
  precip_probability: number
  sunrise: number
  sunset: number
}

export interface SynthhomeForecastHour {
  time: number
  local_hour: number
  conditions: string
  icon: string
  air_temperature: number
  wind_avg: number
  precip_probability: number
}

export interface SynthhomeForecast {
  current: Record<string, unknown>
  daily: SynthhomeForecastDay[]
  hourly: SynthhomeForecastHour[]
  fetched_at: string
}

export interface SynthhomeCurrentWeather {
  temp_f: number | null
  humidity: number | null
  wind_avg: number | null
  wind_gust: number | null
  wind_lull: number | null
  wind_dir: number | null
  pressure: number | null
  illuminance: number | null
  uv: number | null
  solar_radiation: number | null
  daily_rain: number | null
  observed_at: string | null
}

export interface SynthhomeWindReading {
  wind_speed: number
  wind_dir: number
  observed_at: string
}

export interface SynthhomeReading {
  source: string
  metric: string
  value: number
  observed_at: string
}

export async function fetchReadings(
  source: string,
  metric: string,
  hours = 2,
): Promise<SynthhomeReading[]> {
  return fetchJSON(`/readings?source=${source}&metric=${metric}&hours=${hours}`)
}

export async function fetchCurrentWeather(): Promise<SynthhomeCurrentWeather> {
  return fetchJSON('/weather/current')
}

export async function fetchForecast(): Promise<SynthhomeForecast | null> {
  return fetchJSON('/weather/forecast')
}

export async function fetchWindHistory(minutes = 30): Promise<SynthhomeWindReading[]> {
  return fetchJSON(`/weather/wind?minutes=${minutes}`)
}

// ---------------------------------------------------------------------------
// WebSocket: Real-time energy data via Synthhome
// ---------------------------------------------------------------------------

export interface EnergySnapshot {
  timestamp: string
  readings: Record<string, number>
}

export interface EnergyEvent {
  timestamp: string
  kind: string
  payload: Record<string, unknown>
}

export interface EnergyConnectionOptions {
  onSnapshot: (snapshot: EnergySnapshot) => void
  onEvent: (event: EnergyEvent) => void
  onConnected: () => void
  onDisconnected: () => void
  onError: (error: string) => void
}

export function connectEnergy(options: EnergyConnectionOptions): () => void {
  const wsUrl = SYNTHHOME_URL.replace(/^http/, 'ws')
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let destroyed = false

  function connect() {
    if (destroyed) return

    ws = new WebSocket(`${wsUrl}/ws/enphase/`)

    ws.onopen = () => {
      options.onConnected()
    }

    ws.onmessage = (event) => {
      try {
        const msg: SynthhomeMessage = JSON.parse(event.data)

        switch (msg.type) {
          case 'snapshot':
            options.onSnapshot({
              timestamp: msg.data.timestamp as string,
              readings: msg.data as Record<string, number>,
            })
            break
          case 'grid_state_change':
          case 'battery_full':
          case 'battery_empty':
          case 'battery_fault':
          case 'controller_fault':
          case 'microinverter_offline':
          case 'microinverter_online':
          case 'dead_panel_summary':
          case 'pv_production_started':
          case 'pv_production_stopped':
            options.onEvent({
              timestamp: msg.timestamp,
              kind: msg.type,
              payload: msg.data,
            })
            break
        }
      } catch {
        // Ignore parse errors
      }
    }

    ws.onclose = () => {
      options.onDisconnected()
      if (!destroyed) {
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    ws.onerror = () => {
      options.onError('Synthhome energy WebSocket error')
    }
  }

  connect()

  return () => {
    destroyed = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  }
}

// ---------------------------------------------------------------------------
// REST: Energy data from Synthhome API
// ---------------------------------------------------------------------------

export interface EnergyCurrent {
  // Live power (watts)
  pv_production_w: number | null
  pv_voltage: number | null
  pv_frequency: number | null
  pv_production_phase_a_w: number | null
  pv_production_phase_b_w: number | null
  grid_net_w: number | null
  grid_import_w: number | null
  grid_export_w: number | null
  house_consumption_w: number | null
  self_consumption_w: number | null
  battery_agg_power_w: number | null

  // Battery state
  battery_soc: number | null
  battery_avail_wh: number | null

  // Grid/controller state (strings from Envoy)
  grid_mode: string | null
  mains_state: string | null
  controller_temp_f: number | null

  // Totals (refreshed ~5 min)
  production_today_wh: number | null
  production_seven_day_wh: number | null
  production_lifetime_wh: number | null
  consumption_today_wh: number | null
  consumption_seven_day_wh: number | null
  consumption_lifetime_wh: number | null
  grid_net_lifetime_wh: number | null

  observed_at: string | null
}

export interface BatteryDetail {
  serial: string
  capacity_wh: number
  phase: string
  encharge_rev: number
  bmu_fw_version: string
  installed_at: string | null
  last_seen_at: string | null
  soc: number | null
  raw_power_mw: number | null
  temp_c: number | null
}

export interface MicroinverterDetail {
  serial: string
  max_report_w: number
  last_seen_at: string | null
  last_w: number | null
}

export interface EnergyToday {
  date: string
  baseline_captured_at: string
  grid_import_today_wh: number | null
  grid_export_today_wh: number | null
  battery_charged_today_wh: number | null
  battery_discharged_today_wh: number | null
  peak_production_w_today: number | null
  peak_consumption_w_today: number | null
  max_soc_today: number | null
  min_soc_today: number | null
}

export async function fetchEnergyToday(): Promise<EnergyToday> {
  return fetchJSON('/energy/today')
}

export async function fetchCurrentEnergy(): Promise<EnergyCurrent> {
  return fetchJSON('/energy/current')
}

export async function fetchBatteries(): Promise<BatteryDetail[]> {
  return fetchJSON('/energy/batteries')
}

export async function fetchMicroinverters(): Promise<MicroinverterDetail[]> {
  return fetchJSON('/energy/inverters')
}

// ---------------------------------------------------------------------------
// GitHub Activity (direct API, not via Synthhome)
// ---------------------------------------------------------------------------

const GITHUB_TOKEN = import.meta.env.VITE_GITHUB_TOKEN || ''
const GITHUB_USER = 'bryanveloso'

export interface GitHubCommit {
  sha: string
  message: string
  repo: string
  timestamp: string
  url: string
}

export async function fetchRecentCommits(limit = 20): Promise<GitHubCommit[]> {
  const res = await fetch(
    `https://api.github.com/users/${GITHUB_USER}/events?per_page=100`,
    {
      headers: GITHUB_TOKEN
        ? { Authorization: `Bearer ${GITHUB_TOKEN}` }
        : {},
    },
  )
  if (!res.ok) throw new Error(`GitHub API: ${res.status}`)
  const events = await res.json()

  const commits: GitHubCommit[] = []
  for (const event of events) {
    if (event.type !== 'PushEvent') continue
    const repo = event.repo.name
    for (const commit of event.payload.commits ?? []) {
      commits.push({
        sha: commit.sha.slice(0, 7),
        message: commit.message.split('\n')[0],
        repo: repo.includes('/') ? repo.split('/')[1] : repo,
        timestamp: event.created_at,
        url: `https://github.com/${repo}/commit/${commit.sha}`,
      })
    }
  }

  return commits.slice(0, limit)
}

// ---------------------------------------------------------------------------
// Steam Activity (via Questlog proxy)
// ---------------------------------------------------------------------------

const QUESTLOG_URL = import.meta.env.VITE_QUESTLOG_URL || 'http://saya:7176/api'

export interface SteamPlayer {
  personaName: string
  personaState: number
  currentGame: string | null
  currentGameId: string | null
  avatarUrl: string
}

export interface SteamRecentGame {
  appId: number
  name: string
  playtime2Weeks: number
  playtimeForever: number
  iconUrl: string
}

export async function fetchSteamPlayer(): Promise<SteamPlayer> {
  const res = await fetch(`${QUESTLOG_URL}/steam/player`)
  if (!res.ok) throw new Error(`Questlog Steam: ${res.status}`)
  return res.json()
}

export async function fetchSteamRecentGames(count = 5): Promise<SteamRecentGame[]> {
  const res = await fetch(`${QUESTLOG_URL}/steam/recent?count=${count}`)
  if (!res.ok) throw new Error(`Questlog Steam: ${res.status}`)
  return res.json()
}
