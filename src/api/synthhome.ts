const SYNTHHOME_URL = import.meta.env.VITE_SYNTHHOME_URL || 'http://saya:7179'

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

export async function fetchCurrentWeather(): Promise<SynthhomeCurrentWeather> {
  return fetchJSON('/weather/current')
}

export async function fetchForecast(): Promise<SynthhomeForecast | null> {
  return fetchJSON('/weather/forecast')
}

export async function fetchWindHistory(minutes = 30): Promise<SynthhomeWindReading[]> {
  return fetchJSON(`/weather/wind?minutes=${minutes}`)
}
