import { LitElement, html, css, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { HomeAssistant, RoostSchedulerCardConfig, ScheduleGrid, GridConfig } from './types';
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
  @state() private gridConfig: GridConfig = {
    resolution_minutes: 30,
    start_hour: 0,
    end_hour: 24,
    days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
  };

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
      this.loadScheduleData();
    }
  }

  private updateGridConfig(): void {
    if (this.config) {
      this.gridConfig = {
        ...this.gridConfig,
        resolution_minutes: this.config.resolution_minutes || 30
      };
    }
  }

  private async loadScheduleData(): Promise<void> {
    if (!this.hass || !this.config.entity) {
      return;
    }

    try {
      this.loading = true;
      this.error = null;

      // Call the backend service to get schedule data
      const response = await this.hass.callWS({
        type: 'roost_scheduler/get_schedule_grid',
        entity_id: this.config.entity,
      });

      this.scheduleData = response.schedules || {};
    } catch (err) {
      this.error = `Failed to load schedule data: ${err}`;
      console.error('Error loading schedule data:', err);
    } finally {
      this.loading = false;
    }
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
                <div class="version">v${CARD_VERSION}</div>
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

      .version {
        font-size: 0.8em;
        color: var(--secondary-text-color);
        opacity: 0.7;
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