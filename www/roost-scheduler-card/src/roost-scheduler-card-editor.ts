import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { HomeAssistant, RoostSchedulerCardConfig } from './types';

@customElement('roost-scheduler-card-editor')
export class RoostSchedulerCardEditor extends LitElement {
  @property({ attribute: false }) public hass!: HomeAssistant;
  @state() private config!: RoostSchedulerCardConfig;

  public setConfig(config: RoostSchedulerCardConfig): void {
    this.config = { ...config };
  }

  protected render() {
    if (!this.hass || !this.config) {
      return html``;
    }

    // Get all climate entities for the dropdown
    const climateEntities = Object.keys(this.hass.states)
      .filter(entityId => entityId.startsWith('climate.'))
      .map(entityId => ({
        value: entityId,
        label: this.hass.states[entityId].attributes.friendly_name || entityId,
      }));

    return html`
      <div class="card-config">
        <div class="option">
          <label for="entity">Entity (Required)</label>
          <select
            id="entity"
            .value=${this.config.entity || ''}
            @change=${this.handleEntityChange}
          >
            <option value="">Select a climate entity...</option>
            ${climateEntities.map(
              entity => html`
                <option value=${entity.value} ?selected=${entity.value === this.config.entity}>
                  ${entity.label}
                </option>
              `
            )}
          </select>
        </div>

        <div class="option">
          <label for="name">Name (Optional)</label>
          <input
            type="text"
            id="name"
            .value=${this.config.name || ''}
            @input=${this.handleNameChange}
            placeholder="Card title"
          />
        </div>

        <div class="option">
          <label>
            <input
              type="checkbox"
              .checked=${this.config.show_header !== false}
              @change=${this.handleShowHeaderChange}
            />
            Show header
          </label>
        </div>

        <div class="option">
          <label for="resolution">Time Resolution</label>
          <select
            id="resolution"
            .value=${this.config.resolution_minutes || 30}
            @change=${this.handleResolutionChange}
          >
            <option value="15">15 minutes</option>
            <option value="30">30 minutes</option>
            <option value="60">60 minutes</option>
          </select>
        </div>
      </div>
    `;
  }

  private handleEntityChange(ev: Event): void {
    const target = ev.target as HTMLSelectElement;
    if (this.config.entity !== target.value) {
      this.config = { ...this.config, entity: target.value };
      this.dispatchConfigChanged();
    }
  }

  private handleNameChange(ev: Event): void {
    const target = ev.target as HTMLInputElement;
    if (this.config.name !== target.value) {
      this.config = { ...this.config, name: target.value };
      this.dispatchConfigChanged();
    }
  }

  private handleShowHeaderChange(ev: Event): void {
    const target = ev.target as HTMLInputElement;
    if (this.config.show_header !== target.checked) {
      this.config = { ...this.config, show_header: target.checked };
      this.dispatchConfigChanged();
    }
  }

  private handleResolutionChange(ev: Event): void {
    const target = ev.target as HTMLSelectElement;
    const resolution = parseInt(target.value);
    if (this.config.resolution_minutes !== resolution) {
      this.config = { ...this.config, resolution_minutes: resolution };
      this.dispatchConfigChanged();
    }
  }

  private dispatchConfigChanged(): void {
    const event = new CustomEvent('config-changed', {
      detail: { config: this.config },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  static get styles() {
    return css`
      .card-config {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .option {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .option label {
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .option input,
      .option select {
        padding: 8px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font-size: 14px;
      }

      .option input[type="checkbox"] {
        width: auto;
        margin-right: 8px;
      }

      .option label:has(input[type="checkbox"]) {
        flex-direction: row;
        align-items: center;
      }
    `;
  }
}