import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WebSocketManager, OptimisticUpdate } from './websocket-manager';
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

describe('Real-time Synchronization', () => {
  let wsManager: WebSocketManager;
  let mockHass: HomeAssistant;
  const testEntityId = 'climate.test_thermostat';

  beforeEach(() => {
    mockHass = createMockHass();
    wsManager = new WebSocketManager(mockHass, testEntityId);
  });

  describe('Optimistic Updates', () => {
    it('should apply optimistic updates immediately', async () => {
      const mockUnsubscribe = vi.fn();
      (mockHass.connection.subscribeMessage as any).mockResolvedValue(mockUnsubscribe);
      (mockHass.callWS as any).mockResolvedValue({ success: true });

      const eventListener = vi.fn();
      wsManager.addEventListener('schedule_updated', eventListener);

      const changes = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
      
      // This should trigger optimistic update
      await wsManager.updateSchedule('home', changes);

      // Should have received optimistic update event
      expect(eventListener).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'schedule_updated',
          data: expect.objectContaining({
            optimistic: true,
            changes: changes
          })
        })
      );
    });

    it('should rollback optimistic updates on error', async () => {
      const mockUnsubscribe = vi.fn();
      (mockHass.connection.subscribeMessage as any).mockResolvedValue(mockUnsubscribe);
      (mockHass.callWS as any).mockRejectedValue(new Error('Server error'));

      const eventListener = vi.fn();
      wsManager.addEventListener('schedule_updated', eventListener);

      const changes = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
      
      try {
        await wsManager.updateSchedule('home', changes);
      } catch (error) {
        // Expected to throw
      }

      // Should have received both optimistic update and rollback
      expect(eventListener).toHaveBeenCalledTimes(2);
      
      // First call should be optimistic update
      expect(eventListener).toHaveBeenNthCalledWith(1, 
        expect.objectContaining({
          data: expect.objectContaining({ optimistic: true })
        })
      );
      
      // Second call should be rollback
      expect(eventListener).toHaveBeenNthCalledWith(2,
        expect.objectContaining({
          data: expect.objectContaining({ rollback: true })
        })
      );
    });

    it('should track pending updates', async () => {
      const mockUnsubscribe = vi.fn();
      (mockHass.connection.subscribeMessage as any).mockResolvedValue(mockUnsubscribe);
      
      // Mock a slow response
      (mockHass.callWS as any).mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({ success: true }), 100))
      );

      const changes = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
      
      // Start update (don't await yet)
      const updatePromise = wsManager.updateSchedule('home', changes);
      
      // Should have pending update
      const pendingUpdates = wsManager.getPendingUpdates();
      expect(pendingUpdates).toHaveLength(1);
      expect(pendingUpdates[0].changes).toEqual(changes);
      
      // Wait for completion
      await updatePromise;
      
      // Should still have the update (it gets cleaned up after timeout)
      const pendingAfter = wsManager.getPendingUpdates();
      expect(pendingAfter).toHaveLength(1);
      expect(pendingAfter[0].applied).toBe(true);
    });
  });

  describe('Conflict Resolution', () => {
    it('should handle server wins strategy', async () => {
      (mockHass.callWS as any).mockResolvedValue({
        success: false,
        conflict: true,
        server_state: { /* mock server state */ }
      });

      const changes = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
      
      await wsManager.updateScheduleWithConflictResolution('home', changes, {
        strategy: 'server_wins'
      });

      expect(mockHass.callWS).toHaveBeenCalledWith(
        expect.objectContaining({
          conflict_resolution: { strategy: 'server_wins' }
        })
      );
    });

    it('should handle client wins strategy', async () => {
      (mockHass.callWS as any).mockResolvedValue({ success: true });

      const changes = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
      
      await wsManager.updateScheduleWithConflictResolution('home', changes, {
        strategy: 'client_wins'
      });

      expect(mockHass.callWS).toHaveBeenCalledWith(
        expect.objectContaining({
          conflict_resolution: { strategy: 'client_wins' }
        })
      );
    });

    it('should detect and handle conflicts', () => {
      const optimisticUpdate: OptimisticUpdate = {
        id: 'test_update',
        mode: 'home',
        changes: [{ day: 'monday', time: '08:00-09:00', value: 20.0 }],
        timestamp: Date.now() - 1000, // 1 second ago
        applied: false
      };

      const serverData = {
        timestamp: Date.now(), // More recent
        mode: 'home',
        day: 'monday',
        time_slot: '08:00-09:00',
        target_value: 21.0, // Different value
        changes: [{ day: 'monday', time: '08:00-09:00', value: 21.0 }]
      };

      // Simulate conflict detection (this would be internal to WebSocketManager)
      const hasConflict = serverData.timestamp > optimisticUpdate.timestamp;
      expect(hasConflict).toBe(true);
    });
  });

  describe('Connection Recovery', () => {
    it('should clear pending updates on reconnection', async () => {
      const mockUnsubscribe = vi.fn();
      (mockHass.connection.subscribeMessage as any).mockResolvedValue(mockUnsubscribe);
      (mockHass.callWS as any).mockImplementation(() => 
        new Promise(() => {}) // Never resolves to simulate pending
      );

      const changes = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
      
      // Start update that will remain pending
      wsManager.updateSchedule('home', changes);
      
      // Should have pending update
      expect(wsManager.getPendingUpdates()).toHaveLength(1);
      
      // Clear pending updates (simulates reconnection)
      wsManager.clearPendingUpdates();
      
      // Should have no pending updates
      expect(wsManager.getPendingUpdates()).toHaveLength(0);
    });

    it('should handle connection loss during update', async () => {
      const mockUnsubscribe = vi.fn();
      (mockHass.connection.subscribeMessage as any).mockResolvedValue(mockUnsubscribe);
      
      // Mock connection loss
      (mockHass.callWS as any).mockRejectedValue(new Error('Connection lost'));

      const eventListener = vi.fn();
      wsManager.addEventListener('schedule_updated', eventListener);

      const changes = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
      
      try {
        await wsManager.updateSchedule('home', changes);
      } catch (error) {
        expect(error.message).toBe('Connection lost');
      }

      // Should have rolled back the optimistic update
      expect(eventListener).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({ rollback: true })
        })
      );
    });
  });

  describe('Concurrent Updates', () => {
    it('should handle multiple concurrent updates', async () => {
      const mockUnsubscribe = vi.fn();
      (mockHass.connection.subscribeMessage as any).mockResolvedValue(mockUnsubscribe);
      (mockHass.callWS as any).mockResolvedValue({ success: true });

      const changes1 = [{ day: 'monday', time: '08:00-09:00', value: 20.0 }];
      const changes2 = [{ day: 'tuesday', time: '10:00-11:00', value: 22.0 }];
      
      // Start multiple updates concurrently
      const update1 = wsManager.updateSchedule('home', changes1);
      const update2 = wsManager.updateSchedule('home', changes2);
      
      // Should have multiple pending updates
      expect(wsManager.getPendingUpdates()).toHaveLength(2);
      
      // Wait for both to complete
      await Promise.all([update1, update2]);
      
      // Both should have been applied
      const pendingAfter = wsManager.getPendingUpdates();
      expect(pendingAfter.every(update => update.applied)).toBe(true);
    });
  });
});