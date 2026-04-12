import { useEffect, useRef, useState } from 'react'
import { fetchReadings } from '@/api/synthhome'

/**
 * Sparkline hook that backfills from Synthhome history on mount
 * and appends live values from WebSocket updates.
 *
 * @param source - Synthhome source slug (e.g., "tempest", "enphase")
 * @param metric - Metric name (e.g., "temp_f", "pv_production_w")
 * @param liveValue - Current live value from WebSocket (appended on change)
 * @param maxLength - Maximum number of points to keep
 * @param historyHours - How many hours of history to fetch on mount
 */
export function useSparkline(
  source: string,
  metric: string,
  liveValue: number,
  maxLength = 120,
  historyHours = 2,
) {
  const [data, setData] = useState<number[]>([])
  const initialized = useRef(false)
  const prevValue = useRef<number | null>(null)

  // Fetch history on mount
  useEffect(() => {
    let cancelled = false

    async function loadHistory() {
      try {
        const readings = await fetchReadings(source, metric, historyHours)
        if (cancelled) return

        // Readings come newest-first from the API, reverse for chronological order
        const values = readings.map((r) => r.value).reverse()
        // Downsample if we got more than maxLength
        const sampled = values.length > maxLength
          ? values.filter((_, i) => i % Math.ceil(values.length / maxLength) === 0)
          : values

        setData(sampled)
        initialized.current = true
      } catch {
        // History unavailable — sparkline will accumulate from live data
        initialized.current = true
      }
    }

    loadHistory()
    return () => { cancelled = true }
  }, [source, metric, historyHours, maxLength])

  // Append live values
  useEffect(() => {
    if (!initialized.current) return
    if (liveValue === prevValue.current) return

    prevValue.current = liveValue
    setData((prev) => [...prev.slice(-(maxLength - 1)), liveValue])
  }, [liveValue, maxLength])

  return data
}

/**
 * Simple sparkline hook that only accumulates live values (no history backfill).
 * Use for data sources that don't have Synthhome history (e.g., HA-sourced data).
 */
export function useAccumulatingSparkline(value: number, maxLength = 60) {
  const ref = useRef<number[]>([])
  const [history, setHistory] = useState<number[]>([])

  useEffect(() => {
    ref.current = [...ref.current.slice(-(maxLength - 1)), value]
    setHistory([...ref.current])
  }, [value, maxLength])

  return history
}
