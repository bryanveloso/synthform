import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  connectEnergy,
  fetchCurrentEnergy,
  fetchEnergyToday,
  fetchBatteries,
  fetchMicroinverters,
} from '@/api/synthhome'
import type {
  EnergySnapshot,
  EnergyEvent,
  EnergyCurrent,
  EnergyToday,
  BatteryDetail,
  MicroinverterDetail,
} from '@/api/synthhome'

export type {
  EnergySnapshot,
  EnergyEvent,
  EnergyCurrent,
  EnergyToday,
  BatteryDetail,
  MicroinverterDetail,
}

export function useEnphase() {
  const [snapshot, setSnapshot] = useState<EnergySnapshot | null>(null)
  const [events, setEvents] = useState<EnergyEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventsRef = useRef<EnergyEvent[]>([])

  const handleEvent = useCallback((event: EnergyEvent) => {
    eventsRef.current = [event, ...eventsRef.current.slice(0, 49)]
    setEvents([...eventsRef.current])
  }, [])

  useEffect(() => {
    const disconnect = connectEnergy({
      onSnapshot: setSnapshot,
      onEvent: handleEvent,
      onConnected: () => { setIsConnected(true); setError(null) },
      onDisconnected: () => setIsConnected(false),
      onError: (err) => { setError(err); setIsConnected(false) },
    })

    return disconnect
  }, [handleEvent])

  // Derived: any active fault
  const hasFault = events.some(
    (e) => e.kind === 'battery_fault' || e.kind === 'controller_fault',
  )

  return { snapshot, events, hasFault, isConnected, error }
}

export function useEnphaseCurrent() {
  return useQuery<EnergyCurrent>({
    queryKey: ['synthhome', 'energy', 'current'],
    queryFn: fetchCurrentEnergy,
    staleTime: 10_000,
    refetchInterval: 10_000,
  })
}

export function useEnphaseToday() {
  return useQuery<EnergyToday>({
    queryKey: ['synthhome', 'energy', 'today'],
    queryFn: fetchEnergyToday,
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
}

export function useEnphaseBatteries() {
  return useQuery<BatteryDetail[]>({
    queryKey: ['synthhome', 'energy', 'batteries'],
    queryFn: fetchBatteries,
    staleTime: 30_000,
    refetchInterval: 30_000,
  })
}

export function useEnphaseMicroinverters() {
  return useQuery<MicroinverterDetail[]>({
    queryKey: ['synthhome', 'energy', 'inverters'],
    queryFn: fetchMicroinverters,
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  })
}
