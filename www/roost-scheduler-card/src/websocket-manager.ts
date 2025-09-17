/**
 * WebSocket connection manager for real-time communication with Home Assistant backend
 */

import { HomeAssistant } from './types';

export interface WebSocketMessage {
  id?: number;
  type: string;
  [key: string]: any;
}

export interface ScheduleUpdateEvent {
  type: 'schedule_updated';
  data: {
    entity_id: string;
    mode: string;
    day: string;
    time_slot: string;
    target_value: number;
    changes: Array<{
      day: string;
      time: string;
      value: number;
    }>;
  };
}

export interface PresenceChangeEvent {
  type: 'presence_changed';
  data: {
    old_mode: string;
    new_mode: string;
    timestamp: string;
  };
}

export type WebSocketEvent = ScheduleUpdateEvent | PresenceChangeEvent;

export interface ConnectionStatus {
  connected: boolean;
  reconnecting: boolean;
  error?: string;
}

export class WebSocketManager {
  private hass: HomeAssistant;
  private entityId: string;
  private unsubscribeFunction: (() => void) | null = null;
  private connectionStatus: ConnectionStatus = { connected: false, reconnecting: false };
  private eventListeners: Map<string, Set<(event: WebSocketEvent) => void>> = new Map();
  private statusListeners: Set<(status: ConnectionStatus) => void> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private healthCheckInterval: number | null = null;

  constructor(hass: HomeAssistant, entityId: string) {
    this.hass = hass;
    this.entityId = entityId;
  }

  /**
   * Connect to WebSocket and subscribe to updates
   */
  async connect(): Promise<void> {
    try {
      this.updateConnectionStatus({ connected: false, reconnecting: true });

      // Subscribe to real-time updates using HA's subscription system
      const unsubscribe = await this.hass.connection.subscribeMessage(
        (message: any) => this.handleWebSocketMessage(message),
        {
          type: 'roost_scheduler/subscribe_updates',
          entity_id: this.entityId,
        }
      );

      // Store the unsubscribe function
      this.unsubscribeFunction = unsubscribe;
      
      this.connectionStatus = { connected: true, reconnecting: false };
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;

      // Set up connection health monitoring
      this.setupConnectionHealthCheck();

      this.updateConnectionStatus(this.connectionStatus);
      console.log(`WebSocket connected for entity ${this.entityId}`);
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      this.updateConnectionStatus({
        connected: false,
        reconnecting: false,
        error: error instanceof Error ? error.message : 'Connection failed'
      });
      
      // Attempt reconnection with exponential backoff
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket
   */
  async disconnect(): Promise<void> {
    if (this.unsubscribeFunction) {
      try {
        this.unsubscribeFunction();
      } catch (error) {
        console.warn('Error unsubscribing from WebSocket:', error);
      }
      
      this.unsubscribeFunction = null;
    }

    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }

    this.updateConnectionStatus({ connected: false, reconnecting: false });
    console.log(`WebSocket disconnected for entity ${this.entityId}`);
  }

  /**
   * Get current schedule grid from backend
   */
  async getScheduleGrid(): Promise<any> {
    try {
      const response = await this.hass.callWS({
        type: 'roost_scheduler/get_schedule_grid',
        entity_id: this.entityId,
      });
      return response;
    } catch (error) {
      console.error('Failed to get schedule grid:', error);
      throw error;
    }
  }

  /**
   * Update schedule on backend
   */
  async updateSchedule(mode: string, changes: Array<{ day: string; time: string; value: number }>): Promise<void> {
    try {
      await this.hass.callWS({
        type: 'roost_scheduler/update_schedule',
        entity_id: this.entityId,
        mode: mode,
        changes: changes,
      });
    } catch (error) {
      console.error('Failed to update schedule:', error);
      throw error;
    }
  }

  /**
   * Add event listener for specific event types
   */
  addEventListener(eventType: string, listener: (event: WebSocketEvent) => void): void {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, new Set());
    }
    this.eventListeners.get(eventType)!.add(listener);
  }

  /**
   * Remove event listener
   */
  removeEventListener(eventType: string, listener: (event: WebSocketEvent) => void): void {
    const listeners = this.eventListeners.get(eventType);
    if (listeners) {
      listeners.delete(listener);
      if (listeners.size === 0) {
        this.eventListeners.delete(eventType);
      }
    }
  }

  /**
   * Add connection status listener
   */
  addStatusListener(listener: (status: ConnectionStatus) => void): void {
    this.statusListeners.add(listener);
    // Immediately notify with current status
    listener(this.connectionStatus);
  }

  /**
   * Remove connection status listener
   */
  removeStatusListener(listener: (status: ConnectionStatus) => void): void {
    this.statusListeners.delete(listener);
  }

  /**
   * Get current connection status
   */
  getConnectionStatus(): ConnectionStatus {
    return { ...this.connectionStatus };
  }

  private handleWebSocketMessage(message: any): void {
    try {
      // Handle subscription event messages
      if (message.event) {
        const event = message.event;
        if (event.type === 'schedule_updated') {
          this.emitEvent({
            type: 'schedule_updated',
            data: event.data
          });
        } else if (event.type === 'presence_changed') {
          this.emitEvent({
            type: 'presence_changed',
            data: event.data
          });
        }
      }
    } catch (error) {
      console.error('Error handling WebSocket message:', error);
    }
  }

  private setupConnectionHealthCheck(): void {
    this.healthCheckInterval = window.setInterval(() => {
      if (!this.hass.connection || !this.hass.connection.connected) {
        this.handleConnectionLoss();
      }
    }, 5000); // Check every 5 seconds
  }

  private handleConnectionLoss(): void {
    if (this.connectionStatus.connected) {
      console.warn('WebSocket connection lost, attempting to reconnect...');
      this.updateConnectionStatus({ connected: false, reconnecting: true });
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.updateConnectionStatus({
        connected: false,
        reconnecting: false,
        error: 'Max reconnection attempts reached'
      });
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);

    setTimeout(() => {
      if (!this.connectionStatus.connected) {
        console.log(`Reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
        this.connect();
      }
    }, delay);
  }

  private updateConnectionStatus(status: ConnectionStatus): void {
    this.connectionStatus = { ...status };
    this.statusListeners.forEach(listener => {
      try {
        listener(this.connectionStatus);
      } catch (error) {
        console.error('Error in status listener:', error);
      }
    });
  }

  private emitEvent(event: WebSocketEvent): void {
    const listeners = this.eventListeners.get(event.type);
    if (listeners) {
      listeners.forEach(listener => {
        try {
          listener(event);
        } catch (error) {
          console.error('Error in event listener:', error);
        }
      });
    }
  }

  /**
   * Simulate receiving a WebSocket event (for testing or when actual events arrive)
   */
  _simulateEvent(event: WebSocketEvent): void {
    this.emitEvent(event);
  }
}