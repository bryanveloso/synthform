import { createFileRoute } from '@tanstack/react-router'
import { useHomeAssistant } from '@/hooks/use-homeassistant'
import { useTempest, useTempestForecast } from '@/hooks/use-tempest'
import { useEnphase, useEnphaseBatteries, useEnphaseMicroinverters, useEnphaseToday } from '@/hooks/use-enphase'
import { useGitHubCommits } from '@/hooks/use-github'
import { useSteamPlayer, useSteamRecentGames } from '@/hooks/use-steam'
import { useSparkline, useAccumulatingSparkline } from '@/hooks/use-sparkline'
import type { HassEntity } from 'home-assistant-js-websocket'
import type { BatteryDetail } from '@/api/synthhome'

export const Route = createFileRoute('/debug/hud-styles')({
  component: HUDStyles,
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function numState(entity: HassEntity | undefined, fallback = 0): number {
  if (!entity || entity.state === 'unavailable' || entity.state === 'unknown') return fallback
  return parseFloat(entity.state) || fallback
}

// ---------------------------------------------------------------------------
// SVG Components
// ---------------------------------------------------------------------------

// Arc Gauge — circular progress arc with value in center
function ArcGauge({
  value,
  max = 100,
  label,
  unit = '%',
  size = 120,
  strokeWidth = 6,
  color = '#00e5ff',
  trackColor = 'rgba(255,255,255,0.06)',
}: {
  value: number
  max?: number
  label: string
  unit?: string
  size?: number
  strokeWidth?: number
  color?: string
  trackColor?: string
}) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const pct = Math.min(value / max, 1)
  const offset = circumference * (1 - pct)
  const center = size / 2

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={center} cy={center} r={radius} fill="none" stroke={trackColor} strokeWidth={strokeWidth} />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease-out', filter: `drop-shadow(0 0 4px ${color})` }}
        />
      </svg>
      <div className="absolute flex flex-col items-center" style={{ width: size, height: size, justifyContent: 'center' }}>
        <span className="tabular-nums text-lg font-bold" style={{ color }}>{value.toFixed(value % 1 === 0 ? 0 : 1)}</span>
        <span className="text-[9px] text-gray-500">{unit}</span>
      </div>
      <span className="text-[9px] uppercase tracking-wider text-gray-500">{label}</span>
    </div>
  )
}

// Half-arc gauge — 180-degree sweep
function HalfArcGauge({
  value,
  max = 100,
  label,
  unit = '%',
  width = 140,
  height = 80,
  strokeWidth = 6,
  color = '#00ff88',
  trackColor = 'rgba(255,255,255,0.06)',
}: {
  value: number
  max?: number
  label: string
  unit?: string
  width?: number
  height?: number
  strokeWidth?: number
  color?: string
  trackColor?: string
}) {
  const radius = (width - strokeWidth) / 2
  const halfCirc = Math.PI * radius
  const pct = Math.min(value / max, 1)
  const offset = halfCirc * (1 - pct)
  const cx = width / 2
  const cy = height - strokeWidth / 2

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width, height }}>
        <svg width={width} height={height}>
          <path
            d={`M ${strokeWidth / 2},${cy} A ${radius},${radius} 0 0 1 ${width - strokeWidth / 2},${cy}`}
            fill="none"
            stroke={trackColor}
            strokeWidth={strokeWidth}
          />
          <path
            d={`M ${strokeWidth / 2},${cy} A ${radius},${radius} 0 0 1 ${width - strokeWidth / 2},${cy}`}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={halfCirc}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.8s ease-out', filter: `drop-shadow(0 0 4px ${color})` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
          <span className="tabular-nums text-lg font-bold" style={{ color }}>{value.toFixed(value % 1 === 0 ? 0 : 1)}</span>
          <span className="text-[9px] text-gray-500">{unit}</span>
        </div>
      </div>
      <span className="text-[9px] uppercase tracking-wider text-gray-500">{label}</span>
    </div>
  )
}

// Sparkline — SVG path from accumulated history
function Sparkline({
  data,
  width = 200,
  height = 40,
  color = '#00e5ff',
  fillOpacity = 0.15,
  label,
  currentValue,
  unit = '',
}: {
  data: number[]
  width?: number
  height?: number
  color?: string
  fillOpacity?: number
  label?: string
  currentValue?: string
  unit?: string
}) {
  if (data.length < 2) {
    return (
      <div style={{ width, height }} className="flex items-center justify-center text-[10px] text-gray-600">
        Accumulating...
      </div>
    )
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const padding = 2

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = padding + (1 - (v - min) / range) * (height - padding * 2)
    return `${x},${y}`
  })

  const linePath = `M ${points.join(' L ')}`
  const fillPath = `${linePath} L ${width},${height} L 0,${height} Z`

  return (
    <div className="flex flex-col gap-1">
      {(label || currentValue) && (
        <div className="flex items-baseline justify-between">
          {label && <span className="text-[9px] uppercase tracking-wider text-gray-500">{label}</span>}
          {currentValue && (
            <span className="tabular-nums text-xs font-bold" style={{ color }}>
              {currentValue}
              {unit && <span className="ml-1 text-[9px] font-normal text-gray-500">{unit}</span>}
            </span>
          )}
        </div>
      )}
      <svg width={width} height={height} className="overflow-visible">
        <defs>
          <linearGradient id={`sparkFill-${label}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={fillOpacity} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={fillPath} fill={`url(#sparkFill-${label})`} />
        <path
          d={linePath}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          style={{ filter: `drop-shadow(0 0 3px ${color})` }}
        />
        {/* Current value dot */}
        <circle
          cx={width}
          cy={parseFloat(points[points.length - 1].split(',')[1])}
          r={2.5}
          fill={color}
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}
        />
      </svg>
    </div>
  )
}

// Wind compass — radial direction indicator
function Compass({
  direction,
  speed,
  gust,
  size = 120,
  color = '#00e5ff',
}: {
  direction: number
  speed: number
  gust: number
  size?: number
  color?: string
}) {
  const center = size / 2
  const outerR = (size - 4) / 2
  const innerR = outerR - 16
  const tickR = outerR - 4

  const cardinals = [
    { label: 'N', angle: 0 },
    { label: 'E', angle: 90 },
    { label: 'S', angle: 180 },
    { label: 'W', angle: 270 },
  ]

  // Arrow pointing in wind direction
  const rad = (direction - 90) * (Math.PI / 180)
  const arrowTip = { x: center + Math.cos(rad) * (innerR - 4), y: center + Math.sin(rad) * (innerR - 4) }
  const arrowBase1 = { x: center + Math.cos(rad + 2.8) * 12, y: center + Math.sin(rad + 2.8) * 12 }
  const arrowBase2 = { x: center + Math.cos(rad - 2.8) * 12, y: center + Math.sin(rad - 2.8) * 12 }

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size}>
        {/* Outer ring */}
        <circle cx={center} cy={center} r={outerR} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
        <circle cx={center} cy={center} r={innerR} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth={1} />

        {/* Tick marks */}
        {Array.from({ length: 36 }).map((_, i) => {
          const angle = (i * 10 - 90) * (Math.PI / 180)
          const isMajor = i % 9 === 0
          const r1 = isMajor ? outerR - 8 : outerR - 4
          return (
            <line
              key={i}
              x1={center + Math.cos(angle) * r1}
              y1={center + Math.sin(angle) * r1}
              x2={center + Math.cos(angle) * tickR}
              y2={center + Math.sin(angle) * tickR}
              stroke={isMajor ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.1)'}
              strokeWidth={isMajor ? 1.5 : 0.5}
            />
          )
        })}

        {/* Cardinal labels */}
        {cardinals.map(({ label, angle }) => {
          const rad = (angle - 90) * (Math.PI / 180)
          const labelR = outerR - 14
          return (
            <text
              key={label}
              x={center + Math.cos(rad) * labelR}
              y={center + Math.sin(rad) * labelR}
              textAnchor="middle"
              dominantBaseline="central"
              fill="rgba(255,255,255,0.4)"
              fontSize={8}
              fontWeight="bold"
              fontFamily="inherit"
            >
              {label}
            </text>
          )
        })}

        {/* Direction arrow */}
        <polygon
          points={`${arrowTip.x},${arrowTip.y} ${arrowBase1.x},${arrowBase1.y} ${arrowBase2.x},${arrowBase2.y}`}
          fill={color}
          style={{ filter: `drop-shadow(0 0 6px ${color})`, transition: 'all 0.8s ease-out' }}
        />

        {/* Center readout */}
        <text x={center} y={center - 4} textAnchor="middle" fill={color} fontSize={14} fontWeight="bold" fontFamily="inherit">
          {speed.toFixed(1)}
        </text>
        <text x={center} y={center + 8} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize={8} fontFamily="inherit">
          mph
        </text>
      </svg>
      <div className="flex gap-3 text-[9px]">
        <span className="text-gray-500">
          GUST <span className="tabular-nums font-bold" style={{ color }}>{gust.toFixed(1)}</span> mph
        </span>
        <span className="text-gray-500">
          DIR <span className="tabular-nums font-bold text-white">{direction.toFixed(0)}°</span>
        </span>
      </div>
    </div>
  )
}

// Horizontal segmented bar
function SegmentBar({
  value,
  max = 100,
  label,
  unit = '%',
  segments = 20,
  color = '#00e5ff',
  warningAt = 75,
  criticalAt = 90,
  warningColor = '#ff8c00',
  criticalColor = '#ff3d3d',
}: {
  value: number
  max?: number
  label: string
  unit?: string
  segments?: number
  color?: string
  warningAt?: number
  criticalAt?: number
  warningColor?: string
  criticalColor?: string
}) {
  const pct = Math.min(value / max, 1)
  const filledCount = Math.round(pct * segments)
  const pctValue = (value / max) * 100

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        <span className="text-[9px] uppercase tracking-wider text-gray-500">{label}</span>
        <span className="tabular-nums text-xs font-bold" style={{ color: pctValue >= criticalAt ? criticalColor : pctValue >= warningAt ? warningColor : color }}>
          {value.toFixed(value % 1 === 0 ? 0 : 1)}
          <span className="ml-1 text-[9px] font-normal text-gray-500">{unit}</span>
        </span>
      </div>
      <div className="flex gap-[2px]">
        {Array.from({ length: segments }).map((_, i) => {
          const segPct = (i / segments) * 100
          const active = i < filledCount
          let segColor = color
          if (segPct >= criticalAt) segColor = criticalColor
          else if (segPct >= warningAt) segColor = warningColor

          return (
            <div
              key={i}
              className="h-2 flex-1 rounded-[1px]"
              style={{
                backgroundColor: active ? segColor : 'rgba(255,255,255,0.04)',
                boxShadow: active ? `0 0 4px ${segColor}` : 'none',
                transition: 'all 0.3s ease-out',
              }}
            />
          )
        })}
      </div>
    </div>
  )
}

// Large numeric readout
function BigNumber({
  value,
  unit,
  label,
  color = '#e8f0fe',
  size = 'lg',
}: {
  value: string
  unit?: string
  label: string
  color?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
}) {
  const textSize = { sm: 'text-lg', md: 'text-2xl', lg: 'text-4xl', xl: 'text-5xl' }[size]
  return (
    <div className="flex flex-col">
      <span className="text-[9px] uppercase tracking-wider text-gray-500">{label}</span>
      <div className="flex items-baseline gap-1">
        <span className={`tabular-nums font-bold ${textSize}`} style={{ color }}>{value}</span>
        {unit && <span className="text-sm text-gray-500">{unit}</span>}
      </div>
    </div>
  )
}

// Status dot grid — for lights, devices
function StatusGrid({
  items,
}: {
  items: { label: string; active: boolean; color?: string }[]
}) {
  return (
    <div className="grid grid-cols-3 gap-x-4 gap-y-1.5">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <div
            className="size-2 rounded-full"
            style={{
              backgroundColor: item.active ? (item.color || '#00ff88') : 'rgba(255,255,255,0.1)',
              boxShadow: item.active ? `0 0 6px ${item.color || '#00ff88'}` : 'none',
            }}
          />
          <span className={`text-[10px] ${item.active ? 'text-gray-300' : 'text-gray-600'}`}>{item.label}</span>
        </div>
      ))}
    </div>
  )
}

// Vertical bar (like a level meter)
function VerticalBar({
  value,
  max = 100,
  label,
  height = 80,
  width = 16,
  color = '#00e5ff',
}: {
  value: number
  max?: number
  label: string
  height?: number
  width?: number
  color?: string
}) {
  const pct = Math.min(value / max, 1)

  return (
    <div className="flex flex-col items-center gap-1">
      <span className="tabular-nums text-[10px] font-bold" style={{ color }}>{value.toFixed(0)}</span>
      <div className="relative rounded-sm" style={{ width, height, backgroundColor: 'rgba(255,255,255,0.04)' }}>
        <div
          className="absolute bottom-0 w-full rounded-sm"
          style={{
            height: `${pct * 100}%`,
            backgroundColor: color,
            boxShadow: `0 0 6px ${color}`,
            transition: 'height 0.8s ease-out',
          }}
        />
      </div>
      <span className="text-[8px] uppercase tracking-wider text-gray-500">{label}</span>
    </div>
  )
}

// Energy flow diagram — animated arrows between solar/grid/battery/house
function EnergyFlow({
  solarW,
  houseW,
  gridW,
  batteryW,
  batterySoc,
}: {
  solarW: number
  houseW: number
  gridW: number
  batteryW: number
  batterySoc: number
}) {
  const maxW = Math.max(Math.abs(solarW), Math.abs(houseW), Math.abs(gridW), Math.abs(batteryW), 1)
  const scale = (w: number) => Math.min(Math.abs(w) / maxW, 1)

  const importing = gridW > 0
  const exporting = gridW < 0
  const charging = batteryW < 0
  const discharging = batteryW > 0

  function FlowArrow({ from, to, value, color, active }: { from: string; to: string; value: number; color: string; active: boolean }) {
    const opacity = active ? Math.max(0.3, scale(value)) : 0.05
    const width = active ? Math.max(1, scale(value) * 4) : 0.5
    return (
      <div className="flex items-center gap-1">
        <span className="w-16 text-right text-[8px] uppercase tracking-wider text-gray-500">{from}</span>
        <div className="relative h-1 flex-1 overflow-hidden rounded-full" style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}>
          <div
            className="absolute inset-y-0 left-0 rounded-full"
            style={{
              width: `${(active ? scale(value) : 0) * 100}%`,
              backgroundColor: color,
              opacity,
              boxShadow: active ? `0 0 8px ${color}` : 'none',
              height: width,
              top: '50%',
              transform: 'translateY(-50%)',
              transition: 'all 1s ease-out',
            }}
          />
        </div>
        <span className="w-16 text-[8px] uppercase tracking-wider text-gray-500">{to}</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <FlowArrow from="Solar" to="House" value={solarW} color="#ffd600" active={solarW > 10} />
      <FlowArrow from={importing ? "Grid" : "Solar"} to={importing ? "House" : "Grid"} value={gridW} color={importing ? '#ff8c00' : '#00ff88'} active={Math.abs(gridW) > 10} />
      <FlowArrow from={charging ? "Solar" : "Battery"} to={charging ? "Battery" : "House"} value={batteryW} color={charging ? '#b388ff' : '#00e5ff'} active={Math.abs(batteryW) > 10} />
      <div className="mt-1 flex items-center justify-between text-[10px]">
        <span className="tabular-nums text-gray-400">
          <span className="text-[8px] uppercase tracking-wider text-gray-500">House </span>
          {(houseW / 1000).toFixed(2)} kW
        </span>
        <span className="tabular-nums text-gray-400">
          <span className="text-[8px] uppercase tracking-wider text-gray-500">Battery </span>
          {batterySoc.toFixed(0)}%
        </span>
      </div>
    </div>
  )
}

// Solar panel grid — 45 microinverters as colored cells
function SolarGrid({
  inverters,
}: {
  inverters: { serial: string; lastW: number; maxW: number }[]
}) {
  const maxOutput = Math.max(...inverters.map((i) => i.lastW), 1)

  return (
    <div className="grid grid-cols-9 gap-[2px]">
      {inverters.map((inv) => {
        const intensity = inv.maxW === 0 ? 0 : inv.lastW / Math.max(maxOutput, 1)
        const isDead = inv.maxW === 0
        return (
          <div
            key={inv.serial}
            className="aspect-square rounded-[2px]"
            title={`${inv.serial}: ${inv.lastW}W / ${inv.maxW}W max`}
            style={{
              backgroundColor: isDead
                ? 'rgba(255,60,60,0.2)'
                : intensity > 0
                  ? `rgba(255,214,0,${Math.max(0.1, intensity)})`
                  : 'rgba(255,255,255,0.03)',
              boxShadow: intensity > 0.5 ? `0 0 4px rgba(255,214,0,${intensity * 0.5})` : 'none',
              transition: 'all 1s ease-out',
            }}
          />
        )
      })}
    </div>
  )
}

// Battery quartet — four individual battery units
function BatteryQuartet({
  batteries,
}: {
  batteries: BatteryDetail[]
}) {
  return (
    <div className="flex gap-3">
      {batteries.map((b) => (
        <div key={b.serial} className="flex flex-col items-center gap-1">
          <div className="relative h-16 w-8 rounded-sm" style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}>
            <div
              className="absolute bottom-0 w-full rounded-sm"
              style={{
                height: `${b.soc ?? 0}%`,
                backgroundColor: (b.soc ?? 0) > 80 ? '#00ff88' : (b.soc ?? 0) > 30 ? '#ffd600' : '#ff3d3d',
                boxShadow: `0 0 4px ${(b.soc ?? 0) > 80 ? '#00ff88' : (b.soc ?? 0) > 30 ? '#ffd600' : '#ff3d3d'}`,
                transition: 'height 2s ease-out',
              }}
            />
          </div>
          <span className="tabular-nums text-[10px] font-bold text-gray-300">{(b.soc ?? 0).toFixed(0)}%</span>
          <span className="text-[8px] text-gray-500">{b.temp_c != null ? `${((b.temp_c * 9) / 5 + 32).toFixed(0)}°F` : '—'}</span>
        </div>
      ))}
    </div>
  )
}

// Forecast strip — horizontal hourly timeline
function ForecastStrip({
  hours,
}: {
  hours: { localHour: number; temp: number; precipPct: number; conditions: string; icon: string }[]
}) {
  if (!hours.length) return <div className="text-[10px] text-gray-600">No forecast data</div>

  const maxTemp = Math.max(...hours.map((h) => h.temp))
  const minTemp = Math.min(...hours.map((h) => h.temp))
  const range = maxTemp - minTemp || 1

  return (
    <div className="flex gap-[2px] overflow-hidden">
      {hours.map((h, i) => {
        const tempPct = (h.temp - minTemp) / range
        const hasPrecip = h.precipPct > 0
        return (
          <div key={i} className="flex flex-1 flex-col items-center gap-0.5" title={`${h.conditions} ${h.temp}°F ${h.precipPct}%`}>
            <span className="text-[8px] text-gray-500">{h.localHour}h</span>
            <div className="relative h-8 w-full">
              <div
                className="absolute bottom-0 w-full rounded-t-[1px]"
                style={{
                  height: `${tempPct * 100}%`,
                  backgroundColor: `rgba(255,140,0,${0.3 + tempPct * 0.7})`,
                  transition: 'height 0.5s',
                }}
              />
              {hasPrecip && (
                <div
                  className="absolute top-0 w-full rounded-b-[1px]"
                  style={{
                    height: `${h.precipPct}%`,
                    backgroundColor: 'rgba(0,229,255,0.4)',
                  }}
                />
              )}
            </div>
            <span className="tabular-nums text-[8px] text-gray-400">{h.temp.toFixed(0)}°</span>
          </div>
        )
      })}
    </div>
  )
}

// Commit ticker — scrolling list of recent commits
function CommitTicker({
  commits,
}: {
  commits: { sha: string; message: string; repo: string; timestamp: string }[]
}) {
  if (!commits.length) return <div className="text-[10px] text-gray-600">No commits</div>

  return (
    <div className="flex flex-col gap-1">
      {commits.map((c) => {
        const ago = Math.floor((Date.now() - new Date(c.timestamp).getTime()) / 60000)
        const timeStr = ago < 60 ? `${ago}m` : `${Math.floor(ago / 60)}h`
        return (
          <div key={c.sha} className="flex items-baseline gap-2 text-[10px]">
            <span className="tabular-nums font-bold text-gray-500">{c.sha}</span>
            <span className="truncate text-gray-300">{c.message}</span>
            <span className="ml-auto shrink-0 text-[9px] text-gray-600">{c.repo}</span>
            <span className="shrink-0 text-[9px] text-gray-600">{timeStr}</span>
          </div>
        )
      })}
    </div>
  )
}

// Steam status — currently playing or recent games
function SteamStatus({
  currentGame,
  recentGames,
  personaState,
}: {
  currentGame: string | null
  recentGames: { name: string; playtime2Weeks: number; iconUrl: string }[]
  personaState: number
}) {
  const stateLabels: Record<number, string> = { 0: 'Offline', 1: 'Online', 2: 'Busy', 3: 'Away', 4: 'Snooze', 5: 'Trade', 6: 'Play' }

  if (currentGame) {
    return (
      <div className="flex items-center gap-3">
        <div className="size-2 animate-pulse rounded-full bg-green-400 shadow-[0_0_6px_theme(--color-green-400)]" />
        <div>
          <div className="text-xs font-bold text-white">{currentGame}</div>
          <div className="text-[9px] text-gray-500">Currently playing</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 text-[10px] text-gray-500">
        <div className="size-1.5 rounded-full" style={{ backgroundColor: personaState > 0 ? '#00e5ff' : '#666' }} />
        {stateLabels[personaState] ?? 'Unknown'}
      </div>
      {recentGames.slice(0, 3).map((g) => (
        <div key={g.name} className="flex items-center gap-2 text-[10px]">
          <img src={g.iconUrl} alt="" className="size-4 rounded-[2px]" />
          <span className="truncate text-gray-300">{g.name}</span>
          <span className="ml-auto shrink-0 tabular-nums text-gray-500">{(g.playtime2Weeks / 60).toFixed(1)}h</span>
        </div>
      ))}
    </div>
  )
}

// Day scorecard — today's summary numbers
function DayScorecard({
  productionWh,
  consumptionWh,
  gridImportWh,
  gridExportWh,
  batteryChargedWh,
  batteryDischargedWh,
  commitCount,
}: {
  productionWh: number | null
  consumptionWh: number | null
  gridImportWh: number | null
  gridExportWh: number | null
  batteryChargedWh: number | null
  batteryDischargedWh: number | null
  commitCount: number
}) {
  function Row({ label, value, unit }: { label: string; value: string; unit: string }) {
    return (
      <div className="flex items-baseline justify-between border-b border-white/5 py-0.5">
        <span className="text-[9px] uppercase tracking-wider text-gray-500">{label}</span>
        <span className="tabular-nums text-xs font-bold text-gray-300">
          {value} <span className="text-[9px] font-normal text-gray-500">{unit}</span>
        </span>
      </div>
    )
  }

  const fmt = (wh: number | null) => wh != null ? (wh / 1000).toFixed(2) : '—'

  return (
    <div className="flex flex-col">
      <Row label="Produced" value={fmt(productionWh)} unit="kWh" />
      <Row label="Consumed" value={fmt(consumptionWh)} unit="kWh" />
      <Row label="Grid Import" value={fmt(gridImportWh)} unit="kWh" />
      <Row label="Grid Export" value={fmt(gridExportWh)} unit="kWh" />
      <Row label="Battery In" value={fmt(batteryChargedWh)} unit="kWh" />
      <Row label="Battery Out" value={fmt(batteryDischargedWh)} unit="kWh" />
      <Row label="Commits" value={commitCount.toString()} unit="today" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 rounded border border-white/[0.08] p-4">
      <h2 className="text-[10px] font-bold uppercase tracking-[0.12em] text-gray-400">{title}</h2>
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function HUDStyles() {
  const { entities, isConnected: haConnected } = useHomeAssistant()
  const { observation, rapidWind, lastStrike, isConnected: tempestConnected } = useTempest()
  const { snapshot: energySnapshot, isConnected: enphaseConnected } = useEnphase()
  const { data: batteriesData } = useEnphaseBatteries()
  const { data: invertersData } = useEnphaseMicroinverters()
  const { data: energyToday } = useEnphaseToday()
  const { data: forecast } = useTempestForecast()
  const { data: commits } = useGitHubCommits(15)
  const { data: steamPlayer } = useSteamPlayer()
  const { data: steamGames } = useSteamRecentGames(5)

  // Enphase data (via Synthhome WebSocket — 3s snapshots)
  const energyReadings = energySnapshot?.readings ?? {}
  const solarProd = (energyReadings.pv_production_w as number) ?? 0
  const houseConsumption = (energyReadings.house_consumption_w as number) ?? 0
  const gridImport = (energyReadings.grid_import_w as number) ?? 0
  const gridExport = (energyReadings.grid_export_w as number) ?? 0
  const batteryPct = (energyReadings.battery_soc as number) ?? 0
  const batteryPower = (energyReadings.battery_agg_power_w as number) ?? 0
  const selfConsumption = (energyReadings.self_consumption_w as number) ?? 0

  // HA data (everything not yet in Synthhome)
  const temp = numState(entities['sensor.my_ecobee_temperature'])
  const humidity = numState(entities['sensor.my_ecobee_humidity'])
  const co2 = numState(entities['sensor.my_ecobee_carbon_dioxide'])
  const cpuUsage = numState(entities['sensor.unraid_cpu_usage'])
  const ramUsage = numState(entities['sensor.unraid_ram_usage'])
  const arrayUsage = numState(entities['sensor.unraid_array_usage'])
  const disk1 = numState(entities['sensor.unraid_disk1_usage'])
  const disk2 = numState(entities['sensor.unraid_disk2_usage'])
  const disk3 = numState(entities['sensor.unraid_disk3_usage'])
  const evBattery = numState(entities['sensor.polestar_5857_battery_charge_level'])
  const evRange = numState(entities['sensor.polestar_5857_estimated_range'])
  const co2Intensity = numState(entities['sensor.electricity_maps_co2_intensity'])
  const fossilPct = numState(entities['sensor.electricity_maps_grid_fossil_fuel_percentage'])
  const wifiClients = numState(entities['sensor.exandria'])
  const pm25 = numState(entities['sensor.vital_200s_series_pm2_5'])

  // Tempest data (via Synthhome WebSocket — 3s rapid wind, ~1m observations)
  const readings = observation?.readings ?? {}
  const outdoorTemp = (readings.temp_f as number) ?? 0
  const windAvg = rapidWind?.windSpeedMph ?? (readings.wind_avg_mph as number) ?? 0
  const windGust = (readings.wind_gust_mph as number) ?? 0
  const windDir = rapidWind?.windDir ?? (readings.wind_dir as number) ?? 0
  const pressure = (readings.pressure as number) ?? 0

  // Sparkline histories — Synthhome sources backfill from DB, HA sources accumulate
  const outdoorTempHistory = useSparkline('tempest', 'temp_f', outdoorTemp)
  const windSpeedHistory = useSparkline('tempest', 'rapid_wind_speed', windAvg)
  const solarProdHistory = useSparkline('enphase', 'pv_production_w', solarProd)
  const houseConsumptionHistory = useSparkline('enphase', 'house_consumption_w', houseConsumption)
  const tempHistory = useAccumulatingSparkline(temp)
  const co2History = useAccumulatingSparkline(co2)
  const cpuHistory = useAccumulatingSparkline(cpuUsage)

  // Lights for status grid
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
  const lightItems = lightIds.map((id) => {
    const e = entities[id]
    const name = ((e?.attributes.friendly_name as string) ?? id.split('.')[1]).replace(/ Main Lights| Floor Lamp| Table Lamp| Bar Pendants| Chandelier/g, '')
    return { label: name, active: e?.state === 'on', color: '#ffd600' }
  })

  return (
    <div className="min-h-screen bg-[#0a0e14] p-6 font-mono text-[13px] leading-relaxed text-gray-200 antialiased">
      {/* Header */}
      <div className="mb-6 flex items-center gap-4">
        <h1 className="text-sm font-bold uppercase tracking-[0.12em] text-gray-300">HUD Style Compendium</h1>
        <div className={`flex items-center gap-2 text-[10px] ${haConnected ? 'text-green-400' : 'text-red-400'}`}>
          <span className={`inline-block size-2 rounded-full ${haConnected ? 'bg-green-400 shadow-[0_0_6px_theme(--color-green-400)]' : 'animate-pulse bg-red-400'}`} />
          HA {haConnected ? 'LIVE' : 'OFFLINE'}
        </div>
        <div className={`flex items-center gap-2 text-[10px] ${tempestConnected ? 'text-green-400' : 'text-red-400'}`}>
          <span className={`inline-block size-2 rounded-full ${tempestConnected ? 'bg-green-400 shadow-[0_0_6px_theme(--color-green-400)]' : 'animate-pulse bg-red-400'}`} />
          Tempest {tempestConnected ? 'LIVE' : 'OFFLINE'}
        </div>
        <div className={`flex items-center gap-2 text-[10px] ${enphaseConnected ? 'text-green-400' : 'text-red-400'}`}>
          <span className={`inline-block size-2 rounded-full ${enphaseConnected ? 'bg-green-400 shadow-[0_0_6px_theme(--color-green-400)]' : 'animate-pulse bg-red-400'}`} />
          Enphase {enphaseConnected ? 'LIVE' : 'OFFLINE'}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Arc Gauges */}
        <Section title="Arc Gauges">
          <div className="flex flex-wrap items-start gap-6">
            <div className="relative">
              <ArcGauge value={batteryPct} label="Battery" color="#00ff88" />
            </div>
            <div className="relative">
              <ArcGauge value={cpuUsage} label="CPU" color="#00e5ff" />
            </div>
            <div className="relative">
              <ArcGauge value={ramUsage} label="RAM" color="#b388ff" />
            </div>
            <div className="relative">
              <ArcGauge value={evBattery} label="EV" color="#ffd600" />
            </div>
          </div>
        </Section>

        {/* Half-Arc Gauges */}
        <Section title="Half-Arc Gauges">
          <div className="flex flex-wrap items-start gap-6">
            <HalfArcGauge value={temp} max={100} label="Indoor" unit="°F" color="#ff8c00" />
            <HalfArcGauge value={outdoorTemp} max={120} label="Outdoor" unit="°F" color="#00e5ff" />
            <HalfArcGauge value={humidity} max={100} label="Humidity" unit="%" color="#00ff88" />
          </div>
        </Section>

        {/* Wind Compass */}
        <Section title="Wind Compass">
          <div className="flex justify-center">
            <Compass direction={windDir} speed={windAvg} gust={windGust} size={160} />
          </div>
        </Section>

        {/* Sparklines */}
        <Section title="Sparklines">
          <div className="flex flex-col gap-4">
            <Sparkline data={tempHistory} label="Indoor Temp" currentValue={temp.toFixed(1)} unit="°F" color="#ff8c00" />
            <Sparkline data={outdoorTempHistory} label="Outdoor Temp" currentValue={outdoorTemp.toFixed(1)} unit="°F" color="#00e5ff" />
            <Sparkline data={co2History} label="CO₂" currentValue={co2.toFixed(0)} unit="ppm" color="#00ff88" />
            <Sparkline data={windSpeedHistory} label="Wind Speed" currentValue={windAvg.toFixed(1)} unit="mph" color="#b388ff" />
            <Sparkline data={solarProdHistory} label="Solar" currentValue={(solarProd / 1000).toFixed(2)} unit="kW" color="#ffd600" />
            <Sparkline data={houseConsumptionHistory} label="House" currentValue={(houseConsumption / 1000).toFixed(2)} unit="kW" color="#ff8c00" />
            <Sparkline data={cpuHistory} label="CPU" currentValue={cpuUsage.toFixed(1)} unit="%" color="#ff3d3d" />
          </div>
        </Section>

        {/* Segmented Bars */}
        <Section title="Segmented Bars">
          <div className="flex flex-col gap-3">
            <SegmentBar value={arrayUsage} label="Array" color="#00e5ff" />
            <SegmentBar value={disk1} label="Disk 1" color="#00e5ff" warningAt={85} criticalAt={95} />
            <SegmentBar value={disk2} label="Disk 2" color="#00e5ff" warningAt={85} criticalAt={95} />
            <SegmentBar value={disk3} label="Disk 3" color="#00e5ff" warningAt={85} criticalAt={95} />
            <SegmentBar value={co2} max={2500} label="CO₂" unit="ppm" color="#00ff88" warningAt={40} criticalAt={60} segments={30} />
            <SegmentBar value={fossilPct} label="Grid Fossil" unit="%" color="#ff8c00" warningAt={50} criticalAt={80} />
          </div>
        </Section>

        {/* Vertical Bars */}
        <Section title="Vertical Bars (Level Meters)">
          <div className="flex items-end gap-3">
            <VerticalBar value={disk1} label="D1" color="#00e5ff" />
            <VerticalBar value={disk2} label="D2" color="#00e5ff" />
            <VerticalBar value={disk3} label="D3" color="#00e5ff" />
            <div className="mx-2 h-[80px] w-px bg-white/10" />
            <VerticalBar value={cpuUsage} label="CPU" color="#00ff88" />
            <VerticalBar value={ramUsage} label="RAM" color="#b388ff" />
            <div className="mx-2 h-[80px] w-px bg-white/10" />
            <VerticalBar value={batteryPct} label="BAT" color="#ffd600" />
            <VerticalBar value={evBattery} label="EV" color="#ff8c00" />
          </div>
        </Section>

        {/* Big Numbers */}
        <Section title="Big Numbers">
          <div className="grid grid-cols-2 gap-4">
            <BigNumber value={(solarProd / 1000).toFixed(2)} unit="kW" label="Solar Production" color="#ffd600" />
            <BigNumber value={(houseConsumption / 1000).toFixed(2)} unit="kW" label="House Consumption" color="#ff8c00" />
            <BigNumber value={(gridExport / 1000).toFixed(2)} unit="kW" label="Grid Export" color="#00ff88" />
            <BigNumber value={(batteryPower / 1000).toFixed(2)} unit="kW" label="Battery Power" color={batteryPower > 0 ? '#00e5ff' : '#b388ff'} />
            <BigNumber value={co2Intensity.toFixed(0)} unit="gCO₂" label="Grid Carbon" color="#00e5ff" />
            <BigNumber value={wifiClients.toFixed(0)} unit="devices" label="Network" color="#b388ff" />
            <BigNumber value={pressure.toFixed(2)} unit="inHg" label="Barometric" color="#00e5ff" size="md" />
            <BigNumber value={pm25.toFixed(0)} unit="μg/m³" label="PM2.5" color="#00ff88" size="md" />
          </div>
        </Section>

        {/* Status Grid */}
        <Section title="Status Grid (Lights)">
          <StatusGrid items={lightItems} />
        </Section>

        {/* Mixed: Telemetry + Visual */}
        <Section title="Mixed Panel (EV)">
          <div className="flex items-center gap-6">
            <div className="relative">
              <ArcGauge value={evBattery} label="Charge" color="#ffd600" size={100} />
            </div>
            <div className="flex flex-col gap-1">
              <BigNumber value={evRange.toFixed(0)} unit="mi" label="Range" color="#ffd600" size="md" />
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-[9px] uppercase tracking-wider text-gray-500">Status</span>
                <span className="text-xs font-bold text-gray-300">
                  {entities['sensor.polestar_5857_charging_status']?.state ?? '—'}
                </span>
              </div>
            </div>
          </div>
        </Section>

        {/* Energy Flow */}
        <Section title="Energy Flow">
          <EnergyFlow
            solarW={solarProd}
            houseW={houseConsumption}
            gridW={gridImport - gridExport}
            batteryW={batteryPower}
            batterySoc={batteryPct}
          />
        </Section>

        {/* Solar Panel Grid */}
        <Section title={`Solar Array (${invertersData?.length ?? 0} panels)`}>
          {invertersData?.length ? (
            <SolarGrid
              inverters={invertersData.map((inv) => ({
                serial: inv.serial,
                lastW: inv.last_w ?? 0,
                maxW: inv.max_report_w,
              }))}
            />
          ) : (
            <div className="text-[10px] text-gray-600">Loading inverters...</div>
          )}
        </Section>

        {/* Battery Quartet */}
        <Section title="Battery Quartet">
          {batteriesData?.length ? (
            <BatteryQuartet batteries={batteriesData} />
          ) : (
            <div className="text-[10px] text-gray-600">Loading batteries...</div>
          )}
        </Section>

        {/* Forecast Strip */}
        <Section title="Forecast (24h)">
          <ForecastStrip
            hours={(forecast?.hourly ?? []).slice(0, 24).map((h) => ({
              localHour: h.local_hour,
              temp: h.air_temperature,
              precipPct: h.precip_probability,
              conditions: h.conditions,
              icon: h.icon,
            }))}
          />
        </Section>

        {/* Day Scorecard */}
        <Section title="Day Scorecard">
          <DayScorecard
            productionWh={energyToday?.grid_export_today_wh != null ? (energyReadings.production_today_wh as number) ?? null : null}
            consumptionWh={(energyReadings.consumption_today_wh as number) ?? null}
            gridImportWh={energyToday?.grid_import_today_wh ?? null}
            gridExportWh={energyToday?.grid_export_today_wh ?? null}
            batteryChargedWh={energyToday?.battery_charged_today_wh ?? null}
            batteryDischargedWh={energyToday?.battery_discharged_today_wh ?? null}
            commitCount={commits?.filter((c) => {
              const d = new Date(c.timestamp)
              const now = new Date()
              return d.toDateString() === now.toDateString()
            }).length ?? 0}
          />
        </Section>

        {/* Commit Ticker */}
        <Section title="Git Activity">
          <CommitTicker commits={commits ?? []} />
        </Section>

        {/* Steam */}
        <Section title="Steam">
          <SteamStatus
            currentGame={steamPlayer?.currentGame ?? null}
            recentGames={(steamGames ?? []).map((g) => ({
              name: g.name,
              playtime2Weeks: g.playtime2Weeks,
              iconUrl: g.iconUrl,
            }))}
            personaState={steamPlayer?.personaState ?? 0}
          />
        </Section>
      </div>
    </div>
  )
}
