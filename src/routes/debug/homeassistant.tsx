import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { useHAStates } from '@/hooks/use-homeassistant'
import type { HAState } from '@/hooks/use-homeassistant'

export const Route = createFileRoute('/debug/homeassistant')({
  component: HomeAssistantDebug,
})

// Entity groups we care about for the overlay
const ENTITY_GROUPS: Record<string, string[]> = {
  'Solar & Battery': [
    'sensor.envoy_202440001251_current_power_production',
    'sensor.envoy_202440001251_current_power_consumption',
    'sensor.envoy_202440001251_current_net_power_consumption',
    'sensor.envoy_202440001251_energy_production_today',
    'sensor.envoy_202440001251_battery',
    'sensor.envoy_202440001251_available_battery_energy',
    'sensor.envoy_202440001251_battery_capacity',
    'sensor.envoy_202440001251_reserve_battery_level',
    'sensor.envoy_202440001251_current_battery_discharge',
    'sensor.envoy_202440001251_lifetime_energy_production',
  ],
  'Grid & Carbon': [
    'sensor.electricity_maps_co2_intensity',
    'sensor.electricity_maps_grid_fossil_fuel_percentage',
  ],
  'Climate & Air': [
    'sensor.my_ecobee_temperature',
    'sensor.my_ecobee_humidity',
    'sensor.my_ecobee_air_quality_index',
    'sensor.my_ecobee_vocs',
    'sensor.my_ecobee_carbon_dioxide',
    'sensor.living_room_temperature',
    'weather.forecast_home',
  ],
  'EV (Polestar 3)': [
    'sensor.polestar_5857_battery_charge_level',
    'sensor.polestar_5857_estimated_range',
    'sensor.polestar_5857_charging_status',
    'sensor.polestar_5857_current_odometer',
  ],
  'Server (Unraid)': [
    'sensor.unraid_cpu_usage',
    'sensor.unraid_ram_usage',
    'sensor.unraid_cpu_temperature',
    'sensor.unraid_uptime_status',
    'sensor.unraid_array_usage',
    'sensor.unraid_br0_inbound',
    'sensor.unraid_br0_outbound',
    'binary_sensor.unraid_array_health',
    'binary_sensor.unraid_server_connection',
  ],
  'Network': [
    'sensor.exandria',
    'sensor.dream_machine_pro_state',
    'sensor.dream_machine_pro_uptime_2',
    'sensor.usw_pro_24_poe_state',
    'sensor.usw_pro_24_poe_temperature',
  ],
  'Devices': [
    'sensor.demi_frontmost_app',
    'sensor.one_four_battery_level',
    'sensor.one_four_steps',
    'sensor.ipad_pro_battery_level',
    'sensor.front_door_battery',
    'lock.front_door_lock',
  ],
  Lights: [
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
  ],
}

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function freshnessColor(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const seconds = diff / 1000
  if (seconds < 30) return 'text-green-400'
  if (seconds < 120) return 'text-yellow-400'
  if (seconds < 600) return 'text-orange-400'
  return 'text-red-400'
}

function EntityRow({ entity }: { entity: HAState | undefined; }) {
  if (!entity) return null

  const unit = (entity.attributes.unit_of_measurement as string) ?? ''
  const friendly = (entity.attributes.friendly_name as string) ?? entity.entity_id

  return (
    <div className="flex items-baseline gap-3 py-1 border-b border-gray-800/50">
      <span className="text-gray-500 w-64 shrink-0 truncate" title={entity.entity_id}>
        {friendly}
      </span>
      <span className="text-white font-bold">
        {entity.state}
        {unit && <span className="text-gray-500 font-normal ml-1">{unit}</span>}
      </span>
      <span className={`ml-auto text-xs ${freshnessColor(entity.last_changed)}`} title={entity.last_changed}>
        changed {timeAgo(entity.last_changed)}
      </span>
      <span className={`text-xs ${freshnessColor(entity.last_updated)}`} title={entity.last_updated}>
        updated {timeAgo(entity.last_updated)}
      </span>
    </div>
  )
}

function HomeAssistantDebug() {
  const [interval, setInterval] = useState(5_000)
  const { data: states, isLoading, isError, error, dataUpdatedAt } = useHAStates(interval)

  const stateMap = new Map<string, HAState>()
  if (states) {
    for (const s of states) {
      stateMap.set(s.entity_id, s)
    }
  }

  // Entities not in any group
  const groupedIds = new Set(Object.values(ENTITY_GROUPS).flat())
  const ungrouped = states?.filter((s) => !groupedIds.has(s.entity_id) && s.state !== 'unavailable') ?? []

  return (
    <div className="min-h-screen bg-black text-white p-6 font-mono text-xs">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl mb-1 text-chalk">Home Assistant Debug</h1>
        <p className="text-gray-500">Testing entity freshness and poll latency</p>
      </div>

      {/* Controls */}
      <div className="mb-6 flex items-center gap-4">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded ${
          states ? 'bg-green-900/50 text-green-400' : isError ? 'bg-red-900/50 text-red-400' : 'bg-gray-900/50 text-gray-400'
        }`}>
          <span className={`inline-block h-2 w-2 rounded-full ${
            states ? 'bg-green-400' : isError ? 'bg-red-400 animate-pulse' : 'bg-gray-400 animate-pulse'
          }`} />
          {isLoading ? 'Loading...' : isError ? 'Error' : `${states?.length ?? 0} entities`}
        </div>

        {dataUpdatedAt > 0 && (
          <span className="text-gray-500">
            Last fetch: {new Date(dataUpdatedAt).toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 3 })}
          </span>
        )}

        <div className="flex items-center gap-2">
          <span className="text-gray-500">Poll:</span>
          {[1_000, 2_000, 5_000, 10_000, 30_000].map((ms) => (
            <button
              key={ms}
              onClick={() => setInterval(ms)}
              className={`px-2 py-0.5 rounded ${
                interval === ms ? 'bg-cyan-800 text-cyan-200' : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {ms / 1000}s
            </button>
          ))}
        </div>
      </div>

      {isError && (
        <div className="mb-6 p-4 bg-red-900/30 border border-red-800 rounded text-red-400">
          {(error as Error).message}
        </div>
      )}

      {/* Grouped Entities */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        {Object.entries(ENTITY_GROUPS).map(([group, entityIds]) => (
          <div key={group} className="border border-gray-800 rounded p-4 bg-gray-950">
            <h2 className="text-sm font-bold mb-3 text-cyan-400">{group}</h2>
            <div>
              {entityIds.map((id) => (
                <EntityRow key={id} entity={stateMap.get(id)} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Ungrouped (discoverable) */}
      <details className="border border-gray-800 rounded p-4 bg-gray-950">
        <summary className="cursor-pointer text-sm font-bold text-gray-400 hover:text-white">
          All other entities ({ungrouped.length} available)
        </summary>
        <div className="mt-3 max-h-96 overflow-y-auto">
          {ungrouped.map((entity) => (
            <EntityRow key={entity.entity_id} entity={entity} />
          ))}
        </div>
      </details>
    </div>
  )
}