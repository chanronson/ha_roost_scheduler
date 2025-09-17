import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WebSocketManager, ConnectionStatus } from './websocket-manager';
import { HomeAssistant } from './types';

// Mock Home Assistant object
const createMockHass = (): HomeAssistant => ({
  states: {},
  callService: vi.fn(),
  callWS: vi.fn(),
  connection: {
    connected: true,
    subscribeMessage: vi.fn(),
  },
  language: 'en',
  themes: {},
  user: {},
});

describe('WebSocketManager', () => {
  let wsManager: WebSocketManager;
  let mockHass: HomeAssistant;
  const testEntityId = 'climate.test_thermostat';

  beforeEach(() => {
    mockHass = createMockHass();
    wsManager = new WebSocketManager(mockHass, testEntityId);
  });

  it('should initialize with disconnected status', () => {
    const status = wsManager.getConnectionStatus();
    expect(status.connected).toBe(false);
    expect(status.reconnecting).toBe(false);
  });

  it('should connect and update status', async () => {
    const mockUnsubscribe = vi.fn();
    (mockHass.connection.subscribeMessage as any).mockResolvedValue(mockUnsubscribe);

    const statusListener = vi.fn();
    wsManager.addStatusListener(statusListener);

    await wsManager.connect();

    expect(mockHass.connection.subscribeMessage).toHaveBeenCalledWith(
      expect.any(Function),
      {
        type: 'roost_scheduler/subscribe_updates',
        entity_id: testEntityId,
      }
    );

    const finalStatus = wsManager.getConnectionStatus();
    expect(finalStatus.connected).toBe(true);
    expect(finalStatus.reconnecting).toBe(false);
  });

  it('should handle connection errors', async () => {
    const error = new Error('Connection failed');
    (mockHass.connection.subscribeMessage as any).mockRejectedValue(error);

    const statusListener = vi.fn();
    wsManager.addStatusListener(statusListener);

    await wsManager.connect();

    const finalStatus = wsManager.getConnectionStatus();
    expect(finalStatus.connected).toBe(false);
    expect(finalStatus.error).toBe('Connection failed');
  });

  it('should get schedule grid', async () => {
    const mockResponse = {
      schedules: { home: {}, away: {} },
      current_mode: 'home',
      entity_id: testEntityId,
    };
    (mockHass.callWS as any).mockResolvedValue(mockResponse);

    const result = await wsManager.getScheduleGrid();

    expect(mockHass.callWS).toHaveBeenCalledWith({
      type: 'roost_scheduler/get_schedule_grid',
      entity_id: testEntityId,
    });
    expect(result).toEqual(mockResponse);
  });

  it('should update schedule', async () => {
    (mockHass.callWS as any).mockResolvedValue({ success: true });

    const changes = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
    await wsManager.updateSchedule('home', changes);

    expect(mockHass.callWS).toHaveBeenCalledWith({
      type: 'roost_scheduler/update_schedule',
      entity_id: testEntityId,
      mode: 'home',
      changes: changes,
    });
  });

  it('should handle event listeners', () => {
    const listener1 = vi.fn();
    const listener2 = vi.fn();

    wsManager.addEventListener('schedule_updated', listener1);
    wsManager.addEventListener('schedule_updated', listener2);

    // Simulate receiving an event
    wsManager._simulateEvent({
      type: 'schedule_updated',
      data: {
        entity_id: testEntityId,
        mode: 'home',
        day: 'monday',
        time_slot: '08:00-09:00',
        target_value: 20.0,
        changes: [],
      },
    });

    expect(listener1).toHaveBeenCalled();
    expect(listener2).toHaveBeenCalled();

    // Remove one listener
    wsManager.removeEventListener('schedule_updated', listener1);

    // Simulate another event
    wsManager._simulateEvent({
      type: 'schedule_updated',
      data: {
        entity_id: testEntityId,
        mode: 'home',
        day: 'monday',
        time_slot: '08:00-09:00',
        target_value: 21.0,
        changes: [],
      },
    });

    expect(listener1).toHaveBeenCalledTimes(1); // Should not be called again
    expect(listener2).toHaveBeenCalledTimes(2); // Should be called again
  });

  it('should disconnect properly', async () => {
    const mockUnsubscribe = vi.fn();
    (mockHass.connection.subscribeMessage as any).mockResolvedValue(mockUnsubscribe);

    await wsManager.connect();
    await wsManager.disconnect();

    expect(mockUnsubscribe).toHaveBeenCalled();
    
    const status = wsManager.getConnectionStatus();
    expect(status.connected).toBe(false);
  });
});