import { LitElement, html, css, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { ScheduleGrid, GridCell, GridConfig } from './types';

@customElement('schedule-grid')
export class ScheduleGridComponent extends LitElement {
  @property({ type: Object }) scheduleData: ScheduleGrid = {};
  @property({ type: String }) currentMode = 'home';
  @property({ type: Object }) config: GridConfig = {
    resolution_minutes: 30,
    start_hour: 0,
    end_hour: 24,
    days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
  };
  @property({ type: Number }) minValue = 10;
  @property({ type: Number }) maxValue = 30;

  @state() private gridCells: GridCell[][] = [];
  @state() private timeLabels: string[] = [];
  @state() private currentTime = new Date();

  connectedCallback() {
    super.connectedCallback();
    this.updateCurrentTime();
    // Update current time every minute
    setInterval(() => this.updateCurrentTime(), 60000);
  }

  protected willUpdate(changedProps: PropertyValues) {
    if (changedProps.has('scheduleData') || changedProps.has('config') || changedProps.has('currentMode')) {
      this.generateGrid();
    }
  }

  private updateCurrentTime() {
    this.currentTime = new Date();
    this.requestUpdate();
  }

  private generateGrid() {
    const { resolution_minutes, start_hour, end_hour, days } = this.config;
    
    // Generate time labels
    this.timeLabels = [];
    const totalMinutes = (end_hour - start_hour) * 60;
    for (let minutes = 0; minutes < totalMinutes; minutes += resolution_minutes) {
      const hour = Math.floor(minutes / 60) + start_hour;
      const minute = minutes % 60;
      this.timeLabels.push(`${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`);
    }

    // Generate grid cells
    this.gridCells = days.map(day => {
      return this.timeLabels.map(time => {
        const value = this.getValueForSlot(day, time);
        const isCurrentTime = this.isCurrentTimeSlot(day, time);
        
        return {
          day,
          time,
          value,
          isActive: value !== null,
          isCurrentTime
        };
      });
    });
  }

  private getValueForSlot(day: string, time: string): number | null {
    const modeData = this.scheduleData[this.currentMode];
    if (!modeData || !modeData[day]) {
      return null;
    }

    const slots = modeData[day];
    const timeMinutes = this.timeToMinutes(time);

    for (const slot of slots) {
      const startMinutes = this.timeToMinutes(slot.start_time);
      const endMinutes = this.timeToMinutes(slot.end_time);
      
      if (timeMinutes >= startMinutes && timeMinutes < endMinutes) {
        return slot.target_value;
      }
    }

    return null;
  }

  private isCurrentTimeSlot(day: string, time: string): boolean {
    const now = this.currentTime;
    const currentDay = this.getDayName(now.getDay());
    const currentTimeMinutes = now.getHours() * 60 + now.getMinutes();
    const slotTimeMinutes = this.timeToMinutes(time);
    const nextSlotMinutes = slotTimeMinutes + this.config.resolution_minutes;

    return day === currentDay && 
           currentTimeMinutes >= slotTimeMinutes && 
           currentTimeMinutes < nextSlotMinutes;
  }

  private timeToMinutes(time: string): number {
    const [hours, minutes] = time.split(':').map(Number);
    return hours * 60 + minutes;
  }

  private getDayName(dayIndex: number): string {
    const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    return days[dayIndex];
  }

  private getValueColor(value: number | null): string {
    if (value === null) return 'transparent';
    
    // Normalize value between 0 and 1
    const normalized = (value - this.minValue) / (this.maxValue - this.minValue);
    const clamped = Math.max(0, Math.min(1, normalized));
    
    // Create a color gradient from blue (cold) to red (hot)
    const hue = (1 - clamped) * 240; // 240 = blue, 0 = red
    return `hsl(${hue}, 70%, 50%)`;
  }

  private formatValue(value: number | null): string {
    if (value === null) return '';
    return `${value}°`;
  }

  protected render() {
    if (!this.gridCells.length || !Object.keys(this.scheduleData).length) {
      return html`
        <div class="grid-loading">
          <p>Generating schedule grid...</p>
        </div>
      `;
    }

    return html`
      <div class="grid-container">
        <!-- Mode selector -->
        <div class="mode-selector">
          ${Object.keys(this.scheduleData).map(mode => html`
            <button 
              class="mode-button ${mode === this.currentMode ? 'active' : ''}"
              @click=${() => this.selectMode(mode)}
            >
              ${mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          `)}
        </div>

        <!-- Grid -->
        <div class="schedule-grid">
          <!-- Time header -->
          <div class="time-header">
            <div class="day-label"></div>
            ${this.timeLabels.map(time => html`
              <div class="time-label">${time}</div>
            `)}
          </div>

          <!-- Grid rows -->
          ${this.config.days.map((day, dayIndex) => html`
            <div class="grid-row">
              <div class="day-label">${day.charAt(0).toUpperCase() + day.slice(1)}</div>
              ${this.gridCells[dayIndex]?.map(cell => html`
                <div 
                  class="grid-cell ${cell.isActive ? 'active' : ''} ${cell.isCurrentTime ? 'current-time' : ''}"
                  style="background-color: ${this.getValueColor(cell.value)}"
                  title="${cell.day} ${cell.time}${cell.value ? ` - ${this.formatValue(cell.value)}` : ''}"
                >
                  ${cell.isActive ? this.formatValue(cell.value) : ''}
                </div>
              `) || []}
            </div>
          `)}
        </div>

        <!-- Legend -->
        <div class="legend">
          <div class="legend-item">
            <div class="legend-color current-time-indicator"></div>
            <span>Current Time</span>
          </div>
          <div class="legend-item">
            <div class="legend-gradient">
              <div class="gradient-bar"></div>
              <div class="gradient-labels">
                <span>${this.minValue}°</span>
                <span>${this.maxValue}°</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  private selectMode(mode: string) {
    this.currentMode = mode;
    this.dispatchEvent(new CustomEvent('mode-changed', {
      detail: { mode },
      bubbles: true,
      composed: true
    }));
  }

  static get styles() {
    return css`
      :host {
        display: block;
        width: 100%;
      }

      .grid-container {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .grid-loading {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 200px;
        color: var(--secondary-text-color);
      }

      .mode-selector {
        display: flex;
        gap: 8px;
        justify-content: center;
        flex-wrap: wrap;
      }

      .mode-button {
        padding: 8px 16px;
        border: 1px solid var(--divider-color);
        border-radius: 16px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        cursor: pointer;
        transition: all 0.2s ease;
      }

      .mode-button:hover {
        background: var(--secondary-background-color);
      }

      .mode-button.active {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-color: var(--primary-color);
      }

      .schedule-grid {
        display: flex;
        flex-direction: column;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        overflow: hidden;
        background: var(--card-background-color);
      }

      .time-header {
        display: grid;
        grid-template-columns: 100px repeat(auto-fit, minmax(40px, 1fr));
        background: var(--secondary-background-color);
        border-bottom: 1px solid var(--divider-color);
      }

      .time-label {
        padding: 8px 4px;
        text-align: center;
        font-size: 0.8em;
        color: var(--secondary-text-color);
        border-right: 1px solid var(--divider-color);
        writing-mode: vertical-rl;
        text-orientation: mixed;
      }

      .grid-row {
        display: grid;
        grid-template-columns: 100px repeat(auto-fit, minmax(40px, 1fr));
        border-bottom: 1px solid var(--divider-color);
      }

      .grid-row:last-child {
        border-bottom: none;
      }

      .day-label {
        padding: 12px 8px;
        background: var(--secondary-background-color);
        border-right: 1px solid var(--divider-color);
        font-weight: 500;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.9em;
      }

      .grid-cell {
        min-height: 40px;
        border-right: 1px solid var(--divider-color);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8em;
        font-weight: 500;
        color: white;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
        cursor: pointer;
        transition: all 0.2s ease;
        position: relative;
      }

      .grid-cell:hover {
        transform: scale(1.05);
        z-index: 1;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      }

      .grid-cell:not(.active) {
        background: var(--card-background-color) !important;
        color: var(--secondary-text-color);
        text-shadow: none;
      }

      .grid-cell.current-time {
        box-shadow: inset 0 0 0 3px var(--accent-color);
        animation: pulse 2s infinite;
      }

      @keyframes pulse {
        0%, 100% { box-shadow: inset 0 0 0 3px var(--accent-color); }
        50% { box-shadow: inset 0 0 0 3px transparent; }
      }

      .legend {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        font-size: 0.9em;
        color: var(--secondary-text-color);
      }

      .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .current-time-indicator {
        width: 16px;
        height: 16px;
        border: 3px solid var(--accent-color);
        border-radius: 2px;
      }

      .legend-gradient {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .gradient-bar {
        width: 100px;
        height: 16px;
        background: linear-gradient(to right, hsl(240, 70%, 50%), hsl(0, 70%, 50%));
        border-radius: 8px;
        border: 1px solid var(--divider-color);
      }

      .gradient-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.8em;
      }

      /* Responsive design */
      @media (max-width: 768px) {
        .time-header {
          grid-template-columns: 80px repeat(auto-fit, minmax(30px, 1fr));
        }

        .grid-row {
          grid-template-columns: 80px repeat(auto-fit, minmax(30px, 1fr));
        }

        .day-label {
          padding: 8px 4px;
          font-size: 0.8em;
        }

        .time-label {
          padding: 6px 2px;
          font-size: 0.7em;
        }

        .grid-cell {
          min-height: 32px;
          font-size: 0.7em;
        }

        .mode-selector {
          gap: 4px;
        }

        .mode-button {
          padding: 6px 12px;
          font-size: 0.9em;
        }
      }

      @media (max-width: 480px) {
        .time-header {
          grid-template-columns: 60px repeat(auto-fit, minmax(25px, 1fr));
        }

        .grid-row {
          grid-template-columns: 60px repeat(auto-fit, minmax(25px, 1fr));
        }

        .day-label {
          padding: 6px 2px;
          font-size: 0.7em;
        }

        .grid-cell {
          min-height: 28px;
          font-size: 0.6em;
        }

        .legend {
          flex-direction: column;
          gap: 8px;
          align-items: flex-start;
        }
      }
    `;
  }
}