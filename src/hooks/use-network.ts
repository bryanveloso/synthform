import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  connectNetwork,
  fetchNetworkCurrent,
  fetchNetworkDevices,
  fetchPduOutlets,
} from '@/api/synthhome'
import type {
  NetworkSnapshot,
  NetworkEvent,
  NetworkCurrent,
  NetworkDevice,
  PduOutlet,
} from '@/api/synthhome'

export type {
  NetworkSnapshot,
  NetworkEvent,
  NetworkCurrent,
  NetworkDevice,
  PduOutlet,
}

export function useNetwork() {
  const [snapshot, setSnapshot] = useState<NetworkSnapshot | null>(null)
  const [events, setEvents] = useState<NetworkEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventsRef = useRef<NetworkEvent[]>([])

  const handleEvent = useCallback((event: NetworkEvent) => {
    eventsRef.current = [event, ...eventsRef.current.slice(0, 49)]
    setEvents([...eventsRef.current])
  }, [])

  useEffect(() => {
    const disconnect = connectNetwork({
      onSnapshot: setSnapshot,
      onEvent: handleEvent,
      onConnected: () => { setIsConnected(true); setError(null) },
      onDisconnected: () => setIsConnected(false),
      onError: (err) => { setError(err); setIsConnected(false) },
    })

    return disconnect
  }, [handleEvent])

  return { snapshot, events, isConnected, error }
}

export function useNetworkCurrent() {
  return useQuery<NetworkCurrent>({
    queryKey: ['synthhome', 'network', 'current'],
    queryFn: fetchNetworkCurrent,
    staleTime: 10_000,
    refetchInterval: 10_000,
  })
}

export function useNetworkDevices() {
  return useQuery<NetworkDevice[]>({
    queryKey: ['synthhome', 'network', 'devices'],
    queryFn: fetchNetworkDevices,
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
}

export function usePduOutlets() {
  return useQuery<PduOutlet[]>({
    queryKey: ['synthhome', 'network', 'pdu'],
    queryFn: fetchPduOutlets,
    staleTime: 30_000,
    refetchInterval: 30_000,
  })
}
