import { LitElement, html, css, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { HomeAssistant, RoostSchedulerCardConfig, ScheduleGrid, GridConfig } from './types';
import { WebSocketManager, ConnectionStatus, WebSocketEvent } from './websocket-manager';
import './grid-component';

// Card version info for Home Assistant
const CARD_VERSION = '0.3.0';

// Register the card with Home Assistant
(window as any).customCards = (window as any).customCards || [];
(window as any).customCards.push({
  type: 'roost-scheduler-card',
  name: 'Roost Scheduler Card',
  description: 'A card for managing climate schedules with presence-aware automation',
  preview: true,
  documentationURL: 'https://github.com/user/roost-scheduler',
});

@customElement('roost-scheduler-card')
export class RoostSchedulerCard extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @state() private config!: RoostSchedulerCardConfig;
  @state() private scheduleData: ScheduleGrid = {};
  @state() private loading = true;
  @state() private error: string | null = null;
  @state() private currentMode = 'home';
  @state() private connectionStatus: ConnectionStatus = { connected: false, reconnecting: false };
  @state() private gridConfig: GridConfig = {
    resolution_minutes: 30,
    start_hour: 0,
    end_hour: 24,
    days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
  };
  
  private wsManager: WebSocketManager | null = null;

  public static async getConfigElement() {
    await import('./roost-scheduler-card-editor');
    return document.createElement('roost-scheduler-card-editor');
  }

  public static getStubConfig(): RoostSchedulerCardConfig {
    return {
      type: 'custom:roost-scheduler-card',
      entity: '',
      name: 'Roost Scheduler',
      show_header: true,
      resolution_minutes: 30,
    };
  }

  public setConfig(config: RoostSchedulerCardConfig): void {
    if (!config) {
      throw new Error('Invalid configuration');
    }

    if (!config.entity) {
      throw new Error('Entity is required');
    }

    this.config = {
      show_header: true,
      resolution_minutes: 30,
      ...config,
    };
  }

  public getCardSize(): number {
    return 6; // Standard card height units
  }

  protected shouldUpdate(changedProps: PropertyValues): boolean {
    if (!this.config) {
      return false;
    }

    if (changedProps.has('config')) {
      return true;
    }

    if (changedProps.has('hass')) {
      const oldHass = changedProps.get('hass') as HomeAssistant;
      if (!oldHass || oldHass.states[this.config.entity!] !== this.hass.states[this.config.entity!]) {
        return true;
      }
    }

    return false;
  }

  protected updated(changedProps: PropertyValues): void {
    super.updated(changedProps);

    if (changedProps.has('config') || changedProps.has('hass')) {
      this.updateGridConfig();
      this.setupWebSocketConnection();
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.cleanupWebSocketConnection();
  }

  private updateGridConfig(): void {
    if (this.config) {
      this.gridConfig = {
        ...this.gridConfig,
        resolution_minutes: this.config.resolution_minutes || 30
      };
    }
  }

  private async setupWebSocketConnection(): Promise<void> {
    if (!this.hass || !this.config.entity) {
      return;
    }

    // Clean up existing connection
    this.cleanupWebSocketConnection();

    // Create new WebSocket manager
    this.wsManager = new WebSocketManager(this.hass, this.config.entity);

    // Set up event listeners
    this.wsManager.addEventListener('schedule_updated', this.handleScheduleUpdate.bind(this));
    this.wsManager.addEventListener('presence_changed', this.handlePresenceChange.bind(this));
    this.wsManager.addStatusListener(this.handleConnectionStatusChange.bind(this));

    // Load initial data and connect
    await this.loadScheduleData();
    await this.wsManager.connect();
  }

  private cleanupWebSocketConnection(): void {
    if (this.wsManager) {
      this.wsManager.disconnect();
      this.wsManager = null;
    }
  }

  private async loadScheduleData(): Promise<void> {
    if (!this.wsManager) {
      return;
    }

    try {
      this.loading = true;
      this.error = null;

      const response = await this.wsManager.getScheduleGrid();
      this.scheduleData = response.schedules || {};
      this.currentMode = response.current_mode || 'home';
    } catch (err) {
      this.error = `Failed to load schedule data: ${err}`;
      console.error('Error loading schedule data:', err);
    } finally {
      this.loading = false;
    }
  }

  private handleScheduleUpdate(event: WebSocketEvent): void {
    if (event.type === 'schedule_updated') {
      console.log('Received schedule update:', event.data);
      
      const data = event.data as any;
      
      // Handle different types of updates
      if (data.optimistic) {
        // Apply optimistic update to UI immediately
        this.applyOptimisticUpdate(data);
      } else if (data.rollback) {
        // Rollback optimistic update
        this.rollbackOptimisticUpdate(data.update_id);
      } else if (data.conflict) {
        // Handle conflict
        this.handleScheduleConflict(data);
      } else {
        // Normal server update - reload data
        this.loadScheduleData();
      }
    }
  }

  private handlePresenceChange(event: WebSocketEvent): void {
    if (event.type === 'presence_changed') {
      console.log('Presence mode changed:', event.data);
      this.currentMode = event.data.new_mode;
      // Optionally reload data if needed
      this.loadScheduleData();
    }
  }

  private handleConnectionStatusChange(status: ConnectionStatus): void {
    this.connectionStatus = status;
    
    if (status.error && !status.connected && !status.reconnecting) {
      this.error = `Connection error: ${status.error}`;
    } else if (status.connected) {
      // Clear any connection-related errors when reconnected
      if (this.error && this.error.includes('Connection error')) {
        this.error = null;
      }
      
      // Clear any pending optimistic updates on reconnection
      if (this.wsManager) {
        this.wsManager.clearPendingUpdates();
      }
    }
  }

  private applyOptimisticUpdate(data: any): void {
    // Apply changes to local schedule data immediately for responsive UI
    const { mode, changes } = data;
    
    if (!this.scheduleData[mode]) {
      this.scheduleData[mode] = {};
    }
    
    changes.forEach((change: any) => {
      const { day, time, value } = change;
      
      // Update local schedule data
      if (!this.scheduleData[mode][day]) {
        this.scheduleData[mode][day] = [];
      }
      
      // Find and update existing slot or create new one
      const slots = this.scheduleData[mode][day];
      let updated = false;
      
      for (let i = 0; i < slots.length; i++) {
        const slot = slots[i];
        if (slot.start_time <= time && time <= slot.end_time) {
          slot.target_value = value;
          updated = true;
          break;
        }
      }
      
      if (!updated) {
        // Create new slot (simplified)
        slots.push({
          day: day,
          start_time: time,
          end_time: time,
          target_value: value,
          entity_domain: 'climate'
        });
      }
    });
    
    // Trigger re-render
    this.requestUpdate();
  }

  private rollbackOptimisticUpdate(updateId: string): void {
    console.warn('Rolling back optimistic update:', updateId);
    
    // Show error message to user
    this.error = 'Failed to save changes. Reverting to previous state.';
    
    // Reload data from server to get correct state
    this.loadScheduleData();
    
    // Clear error after a delay
    setTimeout(() => {
      if (this.error === 'Failed to save changes. Reverting to previous state.') {
        this.error = null;
      }
    }, 3000);
  }

  private handleScheduleConflict(data: any): void {
    console.warn('Schedule conflict detected:', data);
    
    // Show conflict message to user
    this.error = 'Conflict detected: Your changes conflict with recent updates. Showing latest server state.';
    
    // Reload data to show server state
    this.loadScheduleData();
    
    // Clear error after a delay
    setTimeout(() => {
      if (this.error?.includes('Conflict detected')) {
        this.error = null;
      }
    }, 5000);
  }

  protected render() {
    if (!this.config || !this.hass) {
      return html`
        <ha-card>
          <div class="card-content">
            <div class="error">Configuration required</div>
          </div>
        </ha-card>
      `;
    }

    const entityState = this.hass.states[this.config.entity!];
    if (!entityState) {
      return html`
        <ha-card>
          <div class="card-content">
            <div class="error">Entity "${this.config.entity}" not found</div>
          </div>
        </ha-card>
      `;
    }

    return html`
      <ha-card>
        ${this.config.show_header
          ? html`
              <div class="card-header">
                <div class="name">
                  ${this.config.name || entityState.attributes.friendly_name || this.config.entity}
                </div>
                <div class="header-info">
                  ${this.renderConnectionStatus()}
                  <div class="version">v${CARD_VERSION}</div>
                </div>
              </div>
            `
          : ''}
        
        <div class="card-content">
          ${this.loading
            ? html`<div class="loading">Loading schedule data...</div>`
            : this.error
            ? html`<div class="error">${this.error}</div>`
            : this.renderScheduleGrid()}
        </div>
      </ha-card>
    `;
  }

  private renderScheduleGrid() {
    if (!Object.keys(this.scheduleData).length) {
      return html`
        <div class="no-data">
          <p>No schedule data available.</p>
          <p>Configure your schedule using the Roost Scheduler integration.</p>
        </div>
      `;
    }

    return html`
      <schedule-grid
        .scheduleData=${this.scheduleData}
        .currentMode=${this.currentMode}
        .config=${this.gridConfig}
        .minValue=${this.getEntityMinValue()}
        .maxValue=${this.getEntityMaxValue()}
        @mode-changed=${this.handleModeChanged}
        @schedule-changed=${this.handleScheduleChanged}
        @cell-clicked=${this.handleCellClicked}
      ></schedule-grid>
    `;
  }

  private getEntityMinValue(): number {
    const entityState = this.hass?.states[this.config.entity!];
    return entityState?.attributes?.min_temp || 10;
  }

  private getEntityMaxValue(): number {
    const entityState = this.hass?.states[this.config.entity!];
    return entityState?.attributes?.max_temp || 30;
  }

  private handleModeChanged(event: CustomEvent) {
    this.currentMode = event.detail.mode;
  }

  private async handleScheduleChanged(event: CustomEvent) {
    const { mode, changes } = event.detail;
    
    if (!this.wsManager) {
      this.error = 'WebSocket connection not available';
      return;
    }
    
    try {
      // Use WebSocket manager with optimistic updates
      await this.wsManager.updateSchedule(mode, changes);
      
      // Optimistic update is handled automatically by WebSocket manager
      // Server confirmation or rollback will be handled via WebSocket events
    } catch (err) {
      console.error('Failed to update schedule:', err);
      
      // Error handling is done in rollbackOptimisticUpdate
      // No need to show additional error here as it's already handled
    }
  }

  private handleCellClicked(event: CustomEvent) {
    const { day, time, currentValue } = event.detail;
    console.log(`Cell clicked: ${day} ${time}, current value: ${currentValue}`);
    
    // This could be used for additional functionality like showing detailed info
    // or quick actions for individual cells
  }

  private renderConnectionStatus() {
    const { connected, reconnecting, error } = this.connectionStatus;
    
    if (connected) {
      return html`
        <div class="connection-status connected" title="Connected">
          <div class="status-dot"></div>
        </div>
      `;
    } else if (reconnecting) {
      return html`
        <div class="connection-status reconnecting" title="Reconnecting...">
          <div class="status-dot"></div>
        </div>
      `;
    } else {
      return html`
        <div class="connection-status disconnected" title="${error || 'Disconnected'}">
          <div class="status-dot"></div>
        </div>
      `;
    }
  }

  static get styles() {
    return css`
      :host {
        display: block;
      }

      ha-card {
        height: 100%;
        display: flex;
        flex-direction: column;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        border-bottom: 1px solid var(--divider-color);
      }

      .name {
        font-size: 1.2em;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .header-info {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .version {
        font-size: 0.8em;
        color: var(--secondary-text-color);
        opacity: 0.7;
      }

      .connection-status {
        display: flex;
        align-items: center;
        cursor: help;
      }

      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        transition: background-color 0.3s ease;
      }

      .connection-status.connected .status-dot {
        background-color: var(--success-color, #4caf50);
      }

      .connection-status.reconnecting .status-dot {
        background-color: var(--warning-color, #ff9800);
        animation: pulse 1.5s infinite;
      }

      .connection-status.disconnected .status-dot {
        background-color: var(--error-color, #f44336);
      }

      @keyframes pulse {
        0%, 100% {
          opacity: 1;
        }
        50% {
          opacity: 0.5;
        }
      }

      .card-content {
        padding: 16px;
        flex: 1;
        display: flex;
        flex-direction: column;
      }

      .loading {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 200px;
        color: var(--secondary-text-color);
      }

      .error {
        color: var(--error-color);
        text-align: center;
        padding: 20px;
        background: var(--error-color);
        background-opacity: 0.1;
        border-radius: 4px;
      }

      .no-data {
        text-align: center;
        color: var(--secondary-text-color);
        padding: 40px 20px;
      }

      .no-data p {
        margin: 8px 0;
      }

      .schedule-grid {
        flex: 1;
        min-height: 300px;
      }

      .grid-placeholder {
        text-align: center;
        color: var(--secondary-text-color);
        padding: 40px 20px;
        border: 2px dashed var(--divider-color);
        border-radius: 8px;
      }

      .grid-placeholder p {
        margin: 8px 0;
      }
    `;
  }
}