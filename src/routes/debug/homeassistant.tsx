import { createFileRoute } from '@tanstack/react-router'
import { useHomeAssistant } from '@/hooks/use-homeassistant'
import type { HassEntity } from 'home-assistant-js-websocket'

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
  Network: [
    'sensor.exandria',
    'sensor.dream_machine_pro_state',
    'sensor.dream_machine_pro_uptime_2',
    'sensor.usw_pro_24_poe_state',
    'sensor.usw_pro_24_poe_temperature',
  ],
  Devices: [
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

function EntityRow({ entity }: { entity: HassEntity | undefined }) {
  if (!entity) return null

  const unit = (entity.attributes.unit_of_measurement as string) ?? ''
  const friendly = (entity.attributes.friendly_name as string) ?? entity.entity_id

  return (
    <div className="flex items-baseline justify-between border-b border-white/5 py-1">
      <span className="shrink-0 truncate text-[10px] uppercase tracking-wider text-gray-500" title={entity.entity_id}>
        {friendly}
      </span>
      <span className="min-w-32 text-right tabular-nums font-bold">
        {entity.state}
        {unit && <span className="ml-1 text-[10px] font-normal text-gray-500">{unit}</span>}
      </span>
      <span className={`ml-4 min-w-20 text-right text-[10px] ${freshnessColor(entity.last_changed)}`} title={entity.last_changed}>
        {timeAgo(entity.last_changed)}
      </span>
      <span className={`ml-2 min-w-20 text-right text-[10px] ${freshnessColor(entity.last_updated)}`} title={entity.last_updated}>
        {timeAgo(entity.last_updated)}
      </span>
    </div>
  )
}

function Panel({ title, right, children }: { title: string; right?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col overflow-hidden rounded border border-white/[0.08]">
      <div className="flex min-h-[30px] shrink-0 items-center justify-between border-b border-white/[0.08] bg-white/[0.02] px-2.5 py-1.5">
        <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-gray-400">{title}</span>
        {right && <span className="text-[10px] text-gray-500">{right}</span>}
      </div>
      <div className="flex-1 overflow-y-auto px-2.5 py-2">{children}</div>
    </div>
  )
}

function HomeAssistantDebug() {
  const { entities, isConnected, error } = useHomeAssistant()

  const entityCount = Object.keys(entities).length

  // Entities not in any group
  const groupedIds = new Set(Object.values(ENTITY_GROUPS).flat())
  const ungrouped = Object.values(entities).filter(
    (e) => !groupedIds.has(e.entity_id) && e.state !== 'unavailable',
  )

  return (
    <div className="min-h-screen bg-[#0a0e14] p-4 font-mono text-[13px] leading-relaxed text-gray-200 antialiased">
      {/* Topbar */}
      <div className="mb-4 flex items-center gap-4 rounded border border-white/[0.08] bg-white/[0.02] px-4 py-2">
        <div className={`flex items-center gap-2 ${isConnected ? 'text-green-400' : error ? 'text-red-400' : 'text-gray-400'}`}>
          <span
            className={`inline-block size-2 rounded-full ${
              isConnected
                ? 'bg-green-400 shadow-[0_0_6px_theme(--color-green-400)]'
                : error
                  ? 'animate-pulse bg-red-400'
                  : 'animate-pulse bg-gray-400'
            }`}
          />
          <span className="text-[10px] font-bold uppercase tracking-[0.12em]">
            {isConnected ? 'Live' : error ? 'Error' : 'Connecting'}
          </span>
        </div>

        <span className="text-[10px] text-gray-500">{entityCount} entities</span>
        <span className="text-[10px] text-gray-500">WebSocket</span>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-800 bg-red-900/30 p-3 text-[10px] text-red-400">{error}</div>
      )}

      {/* Entity Panels */}
      <div className="grid grid-cols-2 gap-1">
        {Object.entries(ENTITY_GROUPS).map(([group, entityIds]) => {
          const available = entityIds.filter((id) => entities[id]).length
          return (
            <Panel key={group} title={group} right={`${available}/${entityIds.length}`}>
              {entityIds.map((id) => (
                <EntityRow key={id} entity={entities[id]} />
              ))}
            </Panel>
          )
        })}
      </div>

      {/* Ungrouped */}
      <details className="mt-1">
        <summary className="cursor-pointer rounded border border-white/[0.08] bg-white/[0.02] px-2.5 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-gray-500 hover:text-gray-300">
          All other entities ({ungrouped.length} available)
        </summary>
        <div className="mt-1 max-h-96 overflow-y-auto rounded border border-white/[0.08] px-2.5 py-2">
          {ungrouped.map((entity) => (
            <EntityRow key={entity.entity_id} entity={entity} />
          ))}
        </div>
      </details>
    </div>
  )
}
