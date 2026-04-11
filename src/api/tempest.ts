const TEMPEST_TOKEN = import.meta.env.VITE_TEMPEST_TOKEN || ''
const TEMPEST_DEVICE_ID = import.meta.env.VITE_TEMPEST_DEVICE_ID || ''
const WS_URL = 'wss://ws.weatherflow.com/swd/data'

// obs_st field indices
const OBS_FIELDS = {
  EPOCH: 0,
  WIND_LULL: 1,
  WIND_AVG: 2,
  WIND_GUST: 3,
  WIND_DIR: 4,
  WIND_INTERVAL: 5,
  PRESSURE: 6,
  TEMP_C: 7,
  HUMIDITY: 8,
  ILLUMINANCE: 9,
  UV: 10,
  SOLAR_RADIATION: 11,
  RAIN: 12,
  PRECIP_TYPE: 13,
  LIGHTNING_DIST: 14,
  LIGHTNING_COUNT: 15,
  BATTERY: 16,
  REPORT_INTERVAL: 17,
  DAILY_RAIN: 18,
} as const

export interface TempestObservation {
  epoch: number
  windLull: number
  windAvg: number
  windGust: number
  windDir: number
  pressure: number
  tempC: number
  tempF: number
  humidity: number
  illuminance: number
  uv: number
  solarRadiation: number
  rain: number
  precipType: number
  lightningDist: number
  lightningCount: number
  battery: number
  dailyRain: number
}

export interface TempestRapidWind {
  epoch: number
  windSpeed: number
  windSpeedMph: number
  windDir: number
}

export interface TempestLightningStrike {
  epoch: number
  distance: number
  distanceMi: number
  energy: number
}

export interface TempestState {
  observation: TempestObservation | null
  rapidWind: TempestRapidWind | null
  lastStrike: TempestLightningStrike | null
  isRaining: boolean
}

function cToF(c: number): number {
  return c * 9 / 5 + 32
}

function msToMph(ms: number): number {
  return ms * 2.23694
}

function kmToMi(km: number): number {
  return km * 0.621371
}

function parseObservation(obs: number[]): TempestObservation {
  return {
    epoch: obs[OBS_FIELDS.EPOCH],
    windLull: msToMph(obs[OBS_FIELDS.WIND_LULL] ?? 0),
    windAvg: msToMph(obs[OBS_FIELDS.WIND_AVG] ?? 0),
    windGust: msToMph(obs[OBS_FIELDS.WIND_GUST] ?? 0),
    windDir: obs[OBS_FIELDS.WIND_DIR] ?? 0,
    pressure: obs[OBS_FIELDS.PRESSURE] ?? 0,
    tempC: obs[OBS_FIELDS.TEMP_C] ?? 0,
    tempF: cToF(obs[OBS_FIELDS.TEMP_C] ?? 0),
    humidity: obs[OBS_FIELDS.HUMIDITY] ?? 0,
    illuminance: obs[OBS_FIELDS.ILLUMINANCE] ?? 0,
    uv: obs[OBS_FIELDS.UV] ?? 0,
    solarRadiation: obs[OBS_FIELDS.SOLAR_RADIATION] ?? 0,
    rain: obs[OBS_FIELDS.RAIN] ?? 0,
    precipType: obs[OBS_FIELDS.PRECIP_TYPE] ?? 0,
    lightningDist: kmToMi(obs[OBS_FIELDS.LIGHTNING_DIST] ?? 0),
    lightningCount: obs[OBS_FIELDS.LIGHTNING_COUNT] ?? 0,
    battery: obs[OBS_FIELDS.BATTERY] ?? 0,
    dailyRain: obs[OBS_FIELDS.DAILY_RAIN] ?? 0,
  }
}

function parseRapidWind(ob: number[]): TempestRapidWind {
  return {
    epoch: ob[0],
    windSpeed: ob[1],
    windSpeedMph: msToMph(ob[1]),
    windDir: ob[2],
  }
}

function parseLightningStrike(evt: number[]): TempestLightningStrike {
  return {
    epoch: evt[0],
    distance: evt[1],
    distanceMi: kmToMi(evt[1]),
    energy: evt[2],
  }
}

export interface TempestConnectionOptions {
  onObservation: (obs: TempestObservation) => void
  onRapidWind: (wind: TempestRapidWind) => void
  onLightningStrike: (strike: TempestLightningStrike) => void
  onRainStart: () => void
  onConnected: () => void
  onDisconnected: () => void
  onError: (error: string) => void
}

export function connectTempest(options: TempestConnectionOptions): () => void {
  if (!TEMPEST_TOKEN || !TEMPEST_DEVICE_ID) {
    options.onError('No Tempest token or device ID configured')
    return () => {}
  }

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let destroyed = false

  function connect() {
    if (destroyed) return

    ws = new WebSocket(`${WS_URL}?token=${TEMPEST_TOKEN}`)

    ws.onopen = () => {
      options.onConnected()

      // Subscribe to rapid wind (3s updates)
      ws?.send(JSON.stringify({
        type: 'listen_rapid_start',
        device_id: TEMPEST_DEVICE_ID,
        id: 'rapid-wind',
      }))

      // Subscribe to observations (~1m updates)
      ws?.send(JSON.stringify({
        type: 'listen_start',
        device_id: TEMPEST_DEVICE_ID,
        id: 'observations',
      }))
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        switch (msg.type) {
          case 'obs_st':
            if (msg.obs?.[0]) {
              options.onObservation(parseObservation(msg.obs[0]))
            }
            break
          case 'rapid_wind':
            if (msg.ob) {
              options.onRapidWind(parseRapidWind(msg.ob))
            }
            break
          case 'evt_strike':
            if (msg.evt) {
              options.onLightningStrike(parseLightningStrike(msg.evt))
            }
            break
          case 'evt_precip':
            options.onRainStart()
            break
        }
      } catch {
        // Ignore parse errors for ack messages etc.
      }
    }

    ws.onclose = () => {
      options.onDisconnected()
      if (!destroyed) {
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    ws.onerror = () => {
      options.onError('Tempest WebSocket error')
    }
  }

  connect()

  return () => {
    destroyed = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  }
}
