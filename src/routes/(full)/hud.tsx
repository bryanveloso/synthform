import { createFileRoute } from '@tanstack/react-router'

import { Canvas } from '@/components/ui/canvas'
import { useHomeAssistant } from '@/hooks/use-homeassistant'
import { useTempest, useTempestForecast, useTempestCurrent } from '@/hooks/use-tempest'
import { useEnphase, useEnphaseBatteries, useEnphaseToday, useEnphaseCurrent, useEnphaseMicroinverters } from '@/hooks/use-enphase'
import { useGitHubCommits } from '@/hooks/use-github'
import { useSteamPlayer, useSteamRecentGames } from '@/hooks/use-steam'
import { useSparkline } from '@/hooks/use-sparkline'
import { useAlertQueue } from '@/hooks/use-alerts'
import { useStatus } from '@/hooks/use-status'
import { useMusic } from '@/hooks/use-music'
import { useLimitbreak } from '@/hooks/use-limitbreak'
import type { HassEntity } from 'home-assistant-js-websocket'

export const Route = createFileRoute('/(full)/hud')({
  component: HUD,
})

function numState(entity: HassEntity | undefined, fallback = 0): number {
  if (!entity || entity.state === 'unavailable' || entity.state === 'unknown') return fallback
  return parseFloat(entity.state) || fallback
}

function HUD() {
  // ---------------------------------------------------------------------------
  // Synthfunc (existing overlay data)
  // ---------------------------------------------------------------------------
  const { currentAlert, onAlertComplete, soundEnabled } = useAlertQueue({ soundEnabled: false })
  const { status } = useStatus()
  const { current: musicTrack, source: musicSource, isPlaying } = useMusic()
  const limitbreak = useLimitbreak()

  // ---------------------------------------------------------------------------
  // Home Assistant (HA WebSocket)
  // ---------------------------------------------------------------------------
  const { entities, isConnected: haConnected } = useHomeAssistant()

  // Indoor climate (ecobee)
  const indoorTemp = numState(entities['sensor.my_ecobee_temperature'])
  const indoorHumidity = numState(entities['sensor.my_ecobee_humidity'])
  const indoorCo2 = numState(entities['sensor.my_ecobee_carbon_dioxide'])
  const indoorAqi = numState(entities['sensor.my_ecobee_air_quality_index'])
  const indoorVocs = numState(entities['sensor.my_ecobee_vocs'])
  const barTemp = numState(entities['sensor.living_room_temperature'])

  // Air purifier
  const pm25 = numState(entities['sensor.vital_200s_series_pm2_5'])
  const airQuality = entities['sensor.vital_200s_series_air_quality']?.state ?? '—'
  const filterLife = numState(entities['sensor.vital_200s_series_filter_lifetime'])

  // Server (Unraid)
  const cpuUsage = numState(entities['sensor.unraid_cpu_usage'])
  const ramUsage = numState(entities['sensor.unraid_ram_usage'])
  const cpuTemp = numState(entities['sensor.unraid_cpu_temperature'])
  const uptime = entities['sensor.unraid_uptime_status']?.state ?? '—'
  const arrayUsage = numState(entities['sensor.unraid_array_usage'])
  const disk1 = numState(entities['sensor.unraid_disk1_usage'])
  const disk2 = numState(entities['sensor.unraid_disk2_usage'])
  const disk3 = numState(entities['sensor.unraid_disk3_usage'])
  const netIn = numState(entities['sensor.unraid_br0_inbound'])
  const netOut = numState(entities['sensor.unraid_br0_outbound'])

  // Network (UniFi)
  const wifiClients = numState(entities['sensor.exandria'])

  // EV (Polestar 3)
  const evBattery = numState(entities['sensor.polestar_5857_battery_charge_level'])
  const evRange = numState(entities['sensor.polestar_5857_estimated_range'])
  const evCharging = entities['sensor.polestar_5857_charging_status']?.state ?? '—'

  // Grid carbon
  const co2Intensity = numState(entities['sensor.electricity_maps_co2_intensity'])
  const fossilPct = numState(entities['sensor.electricity_maps_grid_fossil_fuel_percentage'])

  // Lights
  const lightIds = [
    'light.living_room_floor_lamp',
    'light.master_bedroom_table_lamp',
    'light.studio_table_lamp',
    'light.bar_main_lights',
    'light.bar_bar_pendants',
    'light.family_room_main_lights',
    'light.game_room_main_lights',
    'light.game_room_chandelier',
    'light.guest_bedroom_main_lights',
    'light.adu_entry_main_lights',
    'light.adu_kitchen_main_lights',
    'light.adu_hallway_main_lights',
  ]
  const lights = lightIds.map((id) => {
    const e = entities[id]
    return {
      id,
      name: ((e?.attributes.friendly_name as string) ?? id.split('.')[1])
        .replace(/ Main Lights| Floor Lamp| Table Lamp| Bar Pendants| Chandelier/g, ''),
      on: e?.state === 'on',
    }
  })

  // ---------------------------------------------------------------------------
  // Weather (Synthhome WebSocket + REST)
  // ---------------------------------------------------------------------------
  const { observation, rapidWind, lastStrike, isRaining, isConnected: tempestConnected } = useTempest()
  const { data: forecast } = useTempestForecast()
  const { data: currentWeather } = useTempestCurrent()

  const weatherReadings = observation?.readings ?? {}
  const outdoorTemp = (weatherReadings.temp_f as number) ?? 0
  const outdoorHumidity = (weatherReadings.humidity as number) ?? 0
  const windAvg = rapidWind?.windSpeedMph ?? (weatherReadings.wind_avg_mph as number) ?? 0
  const windGust = (weatherReadings.wind_gust_mph as number) ?? 0
  const windDir = rapidWind?.windDir ?? (weatherReadings.wind_dir as number) ?? 0
  const pressure = (weatherReadings.pressure as number) ?? 0
  const uv = (weatherReadings.uv as number) ?? 0
  const solarRadiation = (weatherReadings.solar_radiation as number) ?? 0
  const illuminance = (weatherReadings.illuminance as number) ?? 0
  const dailyRain = (weatherReadings.daily_rain as number) ?? 0

  const forecastHourly = (forecast?.hourly ?? []).slice(0, 24)
  const forecastDaily = forecast?.daily ?? []
  const forecastCurrent = forecast?.current ?? {}

  // ---------------------------------------------------------------------------
  // Energy (Synthhome WebSocket + REST)
  // ---------------------------------------------------------------------------
  const { snapshot: energySnapshot, events: energyEvents, hasFault: energyHasFault, isConnected: enphaseConnected } = useEnphase()
  const { data: energyCurrent } = useEnphaseCurrent()
  const { data: energyToday } = useEnphaseToday()
  const { data: batteries } = useEnphaseBatteries()
  const { data: inverters } = useEnphaseMicroinverters()

  const energy = energySnapshot?.readings ?? {}
  const solarProd = (energy.pv_production_w as number) ?? 0
  const houseConsumption = (energy.house_consumption_w as number) ?? 0
  const gridImport = (energy.grid_import_w as number) ?? 0
  const gridExport = (energy.grid_export_w as number) ?? 0
  const gridNet = (energy.grid_net_w as number) ?? 0
  const batteryPower = (energy.battery_agg_power_w as number) ?? 0
  const batterySoc = (energy.battery_soc as number) ?? 0
  const batteryAvailWh = (energy.battery_avail_wh as number) ?? 0
  const selfConsumption = (energy.self_consumption_w as number) ?? 0

  // Daily totals and peaks
  const productionTodayWh = energyToday?.grid_export_today_wh != null ? (energyCurrent?.production_today_wh ?? null) : null
  const consumptionTodayWh = energyCurrent?.consumption_today_wh ?? null
  const gridImportTodayWh = energyToday?.grid_import_today_wh ?? null
  const gridExportTodayWh = energyToday?.grid_export_today_wh ?? null
  const batteryChargedTodayWh = energyToday?.battery_charged_today_wh ?? null
  const batteryDischargedTodayWh = energyToday?.battery_discharged_today_wh ?? null
  const peakProductionW = energyToday?.peak_production_w_today ?? null
  const peakConsumptionW = energyToday?.peak_consumption_w_today ?? null
  const maxSocToday = energyToday?.max_soc_today ?? null
  const minSocToday = energyToday?.min_soc_today ?? null

  // ---------------------------------------------------------------------------
  // GitHub (direct REST)
  // ---------------------------------------------------------------------------
  const { data: commits } = useGitHubCommits(20)

  // ---------------------------------------------------------------------------
  // Steam (direct REST)
  // ---------------------------------------------------------------------------
  const { data: steamPlayer } = useSteamPlayer()
  const { data: steamGames } = useSteamRecentGames(5)

  // ---------------------------------------------------------------------------
  // Sparklines (Synthhome-backed with history backfill)
  // ---------------------------------------------------------------------------
  const outdoorTempSparkline = useSparkline('tempest', 'temp_f', outdoorTemp)
  const windSparkline = useSparkline('tempest', 'rapid_wind_speed', windAvg)
  const solarSparkline = useSparkline('enphase', 'pv_production_w', solarProd)
  const consumptionSparkline = useSparkline('enphase', 'house_consumption_w', houseConsumption)

  // ---------------------------------------------------------------------------
  // Render — this is your canvas
  // ---------------------------------------------------------------------------
  return (
    <Canvas>
      <div className="size-full bg-[#0a0e14] font-mono text-gray-200">
        {/* Your layout goes here. All data is available above. */}
      </div>
    </Canvas>
  )
}
