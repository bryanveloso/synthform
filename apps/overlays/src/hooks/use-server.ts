import { useEffect, useState, useCallback, useRef } from 'react';

type MessageTypes =
  | 'base:sync'
  | 'base:update'
  | 'timeline:push'
  | 'timeline:sync'
  | 'obs:update'
  | 'obs:sync'
  | 'ticker:sync'
  | 'alert:show'
  | 'alerts:sync'
  | 'alerts:push'
  | 'limitbreak:executed'
  | 'limitbreak:sync'
  | 'limitbreak:update'
  | 'music:sync'
  | 'music:update'

interface ServerMessage {
  type: string;
  payload: any;
  timestamp: string;
  sequence: number;
}

class ServerConnection {
  private ws: WebSocket | null = null;
  private subscribers = new Map<string, Set<(data: any) => void>>();
  private latestData = new Map<string, any>();
  private connectionState = 'disconnected'; // 'disconnected' | 'connecting' | 'connected'
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;

  private getWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // In development, connect to localhost Docker container
    const isDev =
      import.meta.env.DEV || window.location.hostname === 'localhost' || window.location.hostname === 'zelan'
    const host = import.meta.env.VITE_WS_HOST || (isDev ? 'zelan' : 'saya')
    const port = import.meta.env.VITE_WS_PORT || '7175'
    return `${protocol}//${host}:${port}/ws/overlay/`;
  }

  connect() {
    if (this.connectionState !== 'disconnected') {
      return;
    }

    this.connectionState = 'connecting';

    try {
      this.ws = new WebSocket(this.getWebSocketUrl());

      this.ws.onopen = () => {
        console.log('WebSocket connected to server');
        this.connectionState = 'connected';
        this.reconnectAttempts = 0;
        this.notifyConnectionChange(true);
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected from server');
        this.connectionState = 'disconnected';
        this.ws = null;
        this.notifyConnectionChange(false);
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.connectionState = 'disconnected';
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.connectionState = 'disconnected';
      this.scheduleReconnect();
    }
  }

  private handleMessage(event: MessageEvent) {
    try {
      const message: ServerMessage = JSON.parse(event.data);
      const { type, payload } = message;

      // Store latest data for this message type
      this.latestData.set(type, payload);

      // Notify all subscribers for this message type
      const subscribers = this.subscribers.get(type);
      if (subscribers) {
        subscribers.forEach(callback => {
          try {
            callback(payload);
          } catch (error) {
            console.error('Error in subscriber callback:', error);
          }
        });
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    // Only reconnect if we have active subscribers
    if (this.subscribers.size === 0) {
      return;
    }

    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;

    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
    
    setTimeout(() => {
      if (this.connectionState === 'disconnected' && this.subscribers.size > 0) {
        this.connect();
      }
    }, delay);
  }

  subscribe(messageType: string, callback: (data: any) => void): any {
    // Initialize subscriber set if it doesn't exist
    if (!this.subscribers.has(messageType)) {
      this.subscribers.set(messageType, new Set());
    }

    // Add callback to subscribers
    this.subscribers.get(messageType)!.add(callback);

    // Auto-connect if not already connected/connecting
    if (this.connectionState === 'disconnected') {
      this.connect();
    }

    // Return cached data if available
    return this.latestData.get(messageType);
  }

  unsubscribe(messageType: string, callback: (data: any) => void) {
    const subscribers = this.subscribers.get(messageType);
    if (subscribers) {
      subscribers.delete(callback);

      // Clean up empty subscriber sets
      if (subscribers.size === 0) {
        this.subscribers.delete(messageType);
      }
    }

    // If no subscribers left, we could disconnect here
    // But keeping connection alive is probably better for user experience
  }

  isConnected(): boolean {
    return this.connectionState === 'connected';
  }

  private notifyConnectionChange(connected: boolean) {
    // Notify connection state subscribers (added below)
    const connectionSubscribers = this.subscribers.get('__connection__');
    if (connectionSubscribers) {
      connectionSubscribers.forEach(callback => {
        try {
          callback(connected);
        } catch (error) {
          console.error('Error in connection subscriber callback:', error);
        }
      });
    }
  }
}

// Singleton instance
const serverConnection = new ServerConnection();

export function useServer<T extends readonly MessageTypes[]>(messageTypes: T) {
  const [data, setData] = useState<Record<string, any>>({});
  const [isConnected, setIsConnected] = useState(false);
  
  // Use refs to maintain stable callback references
  const callbacksRef = useRef<Map<string, (payload: any) => void>>(new Map());
  const connectionCallbackRef = useRef<((connected: boolean) => void) | undefined>(undefined);

  // Create stable callback for connection state
  const handleConnectionChange = useCallback((connected: boolean) => {
    setIsConnected(connected);
  }, []);

  useEffect(() => {
    // Subscribe to connection state changes
    connectionCallbackRef.current = handleConnectionChange;
    serverConnection.subscribe('__connection__', handleConnectionChange);
    setIsConnected(serverConnection.isConnected());

    return () => {
      if (connectionCallbackRef.current) {
        serverConnection.unsubscribe('__connection__', connectionCallbackRef.current);
      }
    };
  }, [handleConnectionChange]);

  useEffect(() => {
    // Create callbacks for each message type
    const newCallbacks = new Map<string, (payload: any) => void>();

    messageTypes.forEach(messageType => {
      const callback = (payload: any) => {
        setData(prev => ({
          ...prev,
          [messageType]: payload
        }));
      };

      newCallbacks.set(messageType, callback);
      
      // Subscribe and get any cached data
      const cachedData = serverConnection.subscribe(messageType, callback);
      if (cachedData !== undefined) {
        setData(prev => ({
          ...prev,
          [messageType]: cachedData
        }));
      }
    });

    callbacksRef.current = newCallbacks;

    // Cleanup function
    return () => {
      newCallbacks.forEach((callback, messageType) => {
        serverConnection.unsubscribe(messageType, callback);
      });
      callbacksRef.current.clear();
    };
  }, [messageTypes]);

  return {
    data: data as Record<T[number], any>,
    isConnected
  };
}
