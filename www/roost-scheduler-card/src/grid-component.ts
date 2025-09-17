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
  @state() private isDragging = false;
  @state() private dragStartCell: { day: number; time: number } | null = null;
  @state() private dragEndCell: { day: number; time: number } | null = null;
  @state() private selectedCells: Set<string> = new Set();
  @state() private editingValue: number | null = null;
  @state() private showValueEditor = false;
  @state() private editorPosition = { x: 0, y: 0 };
  @state() private copiedCells: Array<{ day: string; time: string; value: number }> = [];
  @state() private showBulkEditor = false;
  @state() private showTemplateMenu = false;
  @state() private templates: Array<{ name: string; data: any }> = [];
  @state() private contextMenuPosition = { x: 0, y: 0 };
  @state() private showContextMenu = false;

  connectedCallback() {
    super.connectedCallback();
    this.updateCurrentTime();
    this.loadTemplatesFromStorage();
    
    // Update current time every minute
    setInterval(() => this.updateCurrentTime(), 60000);
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', this.handleGlobalKeyDown);
    document.addEventListener('click', this.handleGlobalClick);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener('keydown', this.handleGlobalKeyDown);
    document.removeEventListener('click', this.handleGlobalClick);
  }

  private handleGlobalKeyDown = (event: KeyboardEvent) => {
    if (this.selectedCells.size === 0) return;

    // Check if we're in an input field
    const target = event.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

    if (event.ctrlKey || event.metaKey) {
      switch (event.key.toLowerCase()) {
        case 'c':
          event.preventDefault();
          this.copySelection();
          break;
        case 'v':
          event.preventDefault();
          this.pasteSelection();
          break;
        case 'x':
          event.preventDefault();
          this.copySelection();
          this.clearSelection();
          break;
      }
    } else {
      switch (event.key) {
        case 'Delete':
        case 'Backspace':
          event.preventDefault();
          this.clearSelection();
          break;
        case 'Escape':
          this.selectedCells.clear();
          this.showContextMenu = false;
          this.showTemplateMenu = false;
          this.showBulkEditor = false;
          this.requestUpdate();
          break;
      }
    }
  };

  private handleGlobalClick = (event: MouseEvent) => {
    // Close context menu if clicking outside
    if (this.showContextMenu) {
      const target = event.target as HTMLElement;
      if (!target.closest('.context-menu')) {
        this.showContextMenu = false;
        this.requestUpdate();
      }
    }
  };

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
        <!-- Mode selector and toolbar -->
        <div class="toolbar">
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
          
          <div class="toolbar-actions">
            <button 
              class="toolbar-button"
              @click=${() => this.showBulkEditor = true}
              ?disabled=${this.selectedCells.size === 0}
              title="Bulk Edit Selected Cells"
            >
              Bulk Edit
            </button>
            <button 
              class="toolbar-button"
              @click=${() => this.showTemplateMenu = true}
              title="Templates"
            >
              Templates
            </button>
          </div>
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
              ${this.gridCells[dayIndex]?.map((cell, timeIndex) => {
                const cellKey = `${dayIndex}-${timeIndex}`;
                const isSelected = this.selectedCells.has(cellKey);
                return html`
                  <div 
                    class="grid-cell ${cell.isActive ? 'active' : ''} ${cell.isCurrentTime ? 'current-time' : ''} ${isSelected ? 'selected' : ''}"
                    style="background-color: ${this.getValueColor(cell.value)}"
                    title="${cell.day} ${cell.time}${cell.value ? ` - ${this.formatValue(cell.value)}` : ''}"
                    data-day-index="${dayIndex}"
                    data-time-index="${timeIndex}"
                    @mousedown=${(e: MouseEvent) => this.handleCellMouseDown(e, dayIndex, timeIndex)}
                    @click=${(e: MouseEvent) => this.handleCellClick(e, dayIndex, timeIndex)}
                    @contextmenu=${(e: MouseEvent) => this.handleCellRightClick(e, dayIndex, timeIndex)}
                  >
                    ${cell.isActive ? this.formatValue(cell.value) : ''}
                  </div>
                `;
              }) || []}
            </div>
          `)}
        </div>

        <!-- Value Editor -->
        ${this.showValueEditor ? html`
          <div class="value-editor-overlay" @click=${this.closeValueEditor}>
            <div 
              class="value-editor"
              style="left: ${this.editorPosition.x}px; top: ${this.editorPosition.y}px"
              @click=${(e: Event) => e.stopPropagation()}
              @keydown=${this.handleKeyDown}
            >
              <div class="editor-header">
                <span>Set Temperature</span>
                <button class="close-btn" @click=${this.closeValueEditor}>×</button>
              </div>
              <div class="editor-content">
                <div class="value-input-group">
                  <input
                    type="number"
                    .value=${this.editingValue?.toString() || ''}
                    @input=${this.handleValueChange}
                    min=${this.minValue}
                    max=${this.maxValue}
                    step="0.5"
                    class="value-input"
                    placeholder="Temperature"
                    autofocus
                  />
                  <span class="unit">°C</span>
                </div>
                <div class="range-info">
                  Range: ${this.minValue}° - ${this.maxValue}°
                </div>
                <div class="selection-info">
                  ${this.selectedCells.size} cell${this.selectedCells.size !== 1 ? 's' : ''} selected
                </div>
                <div class="editor-actions">
                  <button class="cancel-btn" @click=${this.closeValueEditor}>Cancel</button>
                  <button 
                    class="apply-btn" 
                    @click=${this.applyValueToSelection}
                    ?disabled=${this.editingValue === null || this.editingValue < this.minValue || this.editingValue > this.maxValue}
                  >
                    Apply
                  </button>
                </div>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Context Menu -->
        ${this.showContextMenu ? html`
          <div 
            class="context-menu"
            style="left: ${this.contextMenuPosition.x}px; top: ${this.contextMenuPosition.y}px"
          >
            <button class="context-menu-item" @click=${this.copySelection}>
              Copy (Ctrl+C)
            </button>
            <button 
              class="context-menu-item" 
              @click=${this.pasteSelection}
              ?disabled=${this.copiedCells.length === 0}
            >
              Paste (Ctrl+V)
            </button>
            <button class="context-menu-item" @click=${this.fillSelection}>
              Fill Selection
            </button>
            <button class="context-menu-item" @click=${this.clearSelection}>
              Clear (Delete)
            </button>
            <hr class="context-menu-separator">
            <button class="context-menu-item" @click=${this.saveAsTemplate}>
              Save as Template
            </button>
            <button 
              class="context-menu-item" 
              @click=${() => this.showBulkEditor = true}
            >
              Bulk Edit
            </button>
          </div>
        ` : ''}

        <!-- Bulk Editor -->
        ${this.showBulkEditor ? html`
          <div class="modal-overlay" @click=${() => this.showBulkEditor = false}>
            <div class="bulk-editor" @click=${(e: Event) => e.stopPropagation()}>
              <div class="modal-header">
                <h3>Bulk Edit ${this.selectedCells.size} Cells</h3>
                <button class="close-btn" @click=${() => this.showBulkEditor = false}>×</button>
              </div>
              <div class="bulk-editor-content">
                <div class="bulk-operation">
                  <label>Set all to:</label>
                  <div class="input-group">
                    <input type="number" id="setBulkValue" min=${this.minValue} max=${this.maxValue} step="0.5" />
                    <button @click=${() => {
                      const input = this.shadowRoot?.querySelector('#setBulkValue') as HTMLInputElement;
                      const value = parseFloat(input.value);
                      if (!isNaN(value)) this.applyBulkOperation('set', value);
                    }}>Set</button>
                  </div>
                </div>
                <div class="bulk-operation">
                  <label>Add to all:</label>
                  <div class="input-group">
                    <input type="number" id="addBulkValue" step="0.5" placeholder="1" />
                    <button @click=${() => {
                      const input = this.shadowRoot?.querySelector('#addBulkValue') as HTMLInputElement;
                      const value = parseFloat(input.value) || 1;
                      this.applyBulkOperation('add', value);
                    }}>Add</button>
                  </div>
                </div>
                <div class="bulk-operation">
                  <label>Subtract from all:</label>
                  <div class="input-group">
                    <input type="number" id="subtractBulkValue" step="0.5" placeholder="1" />
                    <button @click=${() => {
                      const input = this.shadowRoot?.querySelector('#subtractBulkValue') as HTMLInputElement;
                      const value = parseFloat(input.value) || 1;
                      this.applyBulkOperation('subtract', value);
                    }}>Subtract</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Template Menu -->
        ${this.showTemplateMenu ? html`
          <div class="modal-overlay" @click=${() => this.showTemplateMenu = false}>
            <div class="template-menu" @click=${(e: Event) => e.stopPropagation()}>
              <div class="modal-header">
                <h3>Schedule Templates</h3>
                <button class="close-btn" @click=${() => this.showTemplateMenu = false}>×</button>
              </div>
              <div class="template-list">
                ${this.templates.length === 0 ? html`
                  <div class="empty-templates">
                    <p>No templates saved yet.</p>
                    <p>Select cells and right-click to save a template.</p>
                  </div>
                ` : this.templates.map((template, index) => html`
                  <div class="template-item">
                    <div class="template-info">
                      <span class="template-name">${template.name}</span>
                      <span class="template-details">
                        ${template.data.cells?.length || 0} cells, ${template.data.mode} mode
                      </span>
                    </div>
                    <div class="template-actions">
                      <button 
                        class="template-action-btn apply-btn"
                        @click=${() => this.loadTemplate(template)}
                        ?disabled=${this.selectedCells.size === 0}
                        title="Apply template to selected area"
                      >
                        Apply
                      </button>
                      <button 
                        class="template-action-btn delete-btn"
                        @click=${() => this.deleteTemplate(index)}
                        title="Delete template"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                `)}
              </div>
            </div>
          </div>
        ` : ''}

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

  private handleCellMouseDown(event: MouseEvent, dayIndex: number, timeIndex: number) {
    event.preventDefault();
    this.isDragging = true;
    this.dragStartCell = { day: dayIndex, time: timeIndex };
    this.dragEndCell = { day: dayIndex, time: timeIndex };
    this.updateSelectedCells();
    
    // Add global mouse event listeners
    document.addEventListener('mousemove', this.handleMouseMove);
    document.addEventListener('mouseup', this.handleMouseUp);
  }

  private handleMouseMove = (event: MouseEvent) => {
    if (!this.isDragging || !this.dragStartCell) return;

    const cell = this.getCellFromMouseEvent(event);
    if (cell) {
      this.dragEndCell = cell;
      this.updateSelectedCells();
    }
  };

  private handleMouseUp = (event: MouseEvent) => {
    if (!this.isDragging) return;

    this.isDragging = false;
    document.removeEventListener('mousemove', this.handleMouseMove);
    document.removeEventListener('mouseup', this.handleMouseUp);

    // Show value editor if we have selected cells
    if (this.selectedCells.size > 0) {
      this.showValueEditor = true;
      this.editorPosition = { x: event.clientX, y: event.clientY };
      this.editingValue = this.getAverageValueFromSelection();
    }
  };

  private getCellFromMouseEvent(event: MouseEvent): { day: number; time: number } | null {
    // Fallback for test environments where elementFromPoint is not available
    if (typeof document.elementFromPoint !== 'function') {
      return null;
    }
    
    const element = document.elementFromPoint(event.clientX, event.clientY);
    if (!element || !element.classList.contains('grid-cell')) return null;

    const dayIndex = parseInt(element.getAttribute('data-day-index') || '-1');
    const timeIndex = parseInt(element.getAttribute('data-time-index') || '-1');

    if (dayIndex >= 0 && timeIndex >= 0) {
      return { day: dayIndex, time: timeIndex };
    }
    return null;
  }

  private updateSelectedCells() {
    if (!this.dragStartCell || !this.dragEndCell) return;

    this.selectedCells.clear();
    
    const startDay = Math.min(this.dragStartCell.day, this.dragEndCell.day);
    const endDay = Math.max(this.dragStartCell.day, this.dragEndCell.day);
    const startTime = Math.min(this.dragStartCell.time, this.dragEndCell.time);
    const endTime = Math.max(this.dragStartCell.time, this.dragEndCell.time);

    for (let day = startDay; day <= endDay; day++) {
      for (let time = startTime; time <= endTime; time++) {
        this.selectedCells.add(`${day}-${time}`);
      }
    }
    this.requestUpdate();
  }

  private getAverageValueFromSelection(): number {
    let total = 0;
    let count = 0;

    this.selectedCells.forEach(cellKey => {
      const [dayIndex, timeIndex] = cellKey.split('-').map(Number);
      const cell = this.gridCells[dayIndex]?.[timeIndex];
      if (cell?.value !== null) {
        total += cell.value;
        count++;
      }
    });

    return count > 0 ? Math.round(total / count) : Math.round((this.minValue + this.maxValue) / 2);
  }

  private handleValueChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const value = parseFloat(input.value);
    
    if (!isNaN(value)) {
      this.editingValue = Math.max(this.minValue, Math.min(this.maxValue, value));
    }
  }

  private applyValueToSelection() {
    if (this.editingValue === null || this.selectedCells.size === 0) return;

    const changes: Array<{ day: string; time: string; value: number }> = [];

    this.selectedCells.forEach(cellKey => {
      const [dayIndex, timeIndex] = cellKey.split('-').map(Number);
      const day = this.config.days[dayIndex];
      const time = this.timeLabels[timeIndex];
      
      if (day && time) {
        changes.push({ day, time, value: this.editingValue! });
      }
    });

    // Emit schedule change event
    this.dispatchEvent(new CustomEvent('schedule-changed', {
      detail: { 
        mode: this.currentMode,
        changes 
      },
      bubbles: true,
      composed: true
    }));

    this.closeValueEditor();
  }

  private closeValueEditor() {
    this.showValueEditor = false;
    this.editingValue = null;
    this.selectedCells.clear();
    this.dragStartCell = null;
    this.dragEndCell = null;
    this.requestUpdate();
  }

  private handleCellClick(event: MouseEvent, dayIndex: number, timeIndex: number) {
    // Single click for quick edit
    if (!this.isDragging) {
      const day = this.config.days[dayIndex];
      const time = this.timeLabels[timeIndex];
      const currentValue = this.gridCells[dayIndex]?.[timeIndex]?.value;

      this.dispatchEvent(new CustomEvent('cell-clicked', {
        detail: { 
          day, 
          time, 
          currentValue,
          dayIndex,
          timeIndex
        },
        bubbles: true,
        composed: true
      }));
    }
  }

  private handleCellRightClick(event: MouseEvent, dayIndex: number, timeIndex: number) {
    event.preventDefault();
    
    // Select the cell if not already selected
    const cellKey = `${dayIndex}-${timeIndex}`;
    if (!this.selectedCells.has(cellKey)) {
      this.selectedCells.clear();
      this.selectedCells.add(cellKey);
      this.requestUpdate();
    }

    this.contextMenuPosition = { x: event.clientX, y: event.clientY };
    this.showContextMenu = true;
  }

  private copySelection() {
    this.copiedCells = [];
    
    this.selectedCells.forEach(cellKey => {
      const [dayIndex, timeIndex] = cellKey.split('-').map(Number);
      const day = this.config.days[dayIndex];
      const time = this.timeLabels[timeIndex];
      const cell = this.gridCells[dayIndex]?.[timeIndex];
      
      if (day && time && cell?.value !== null) {
        this.copiedCells.push({ day, time, value: cell.value });
      }
    });

    this.showContextMenu = false;
    
    // Show feedback
    this.dispatchEvent(new CustomEvent('show-message', {
      detail: { 
        message: `Copied ${this.copiedCells.length} cell${this.copiedCells.length !== 1 ? 's' : ''}`,
        type: 'info'
      },
      bubbles: true,
      composed: true
    }));
  }

  private pasteSelection() {
    if (this.copiedCells.length === 0) return;

    const changes: Array<{ day: string; time: string; value: number }> = [];
    
    // Get the first selected cell as the paste anchor
    const firstSelectedKey = Array.from(this.selectedCells)[0];
    if (!firstSelectedKey) return;

    const [anchorDayIndex, anchorTimeIndex] = firstSelectedKey.split('-').map(Number);
    
    // Calculate relative positions from the first copied cell
    const firstCopiedCell = this.copiedCells[0];
    const firstCopiedDayIndex = this.config.days.indexOf(firstCopiedCell.day);
    const firstCopiedTimeIndex = this.timeLabels.indexOf(firstCopiedCell.time);

    this.copiedCells.forEach(copiedCell => {
      const copiedDayIndex = this.config.days.indexOf(copiedCell.day);
      const copiedTimeIndex = this.timeLabels.indexOf(copiedCell.time);
      
      // Calculate relative offset
      const dayOffset = copiedDayIndex - firstCopiedDayIndex;
      const timeOffset = copiedTimeIndex - firstCopiedTimeIndex;
      
      // Apply offset to anchor position
      const targetDayIndex = anchorDayIndex + dayOffset;
      const targetTimeIndex = anchorTimeIndex + timeOffset;
      
      // Check bounds
      if (targetDayIndex >= 0 && targetDayIndex < this.config.days.length &&
          targetTimeIndex >= 0 && targetTimeIndex < this.timeLabels.length) {
        
        const targetDay = this.config.days[targetDayIndex];
        const targetTime = this.timeLabels[targetTimeIndex];
        
        changes.push({ day: targetDay, time: targetTime, value: copiedCell.value });
      }
    });

    if (changes.length > 0) {
      this.dispatchEvent(new CustomEvent('schedule-changed', {
        detail: { 
          mode: this.currentMode,
          changes 
        },
        bubbles: true,
        composed: true
      }));
    }

    this.showContextMenu = false;
  }

  private clearSelection() {
    const changes: Array<{ day: string; time: string; value: number | null }> = [];
    
    this.selectedCells.forEach(cellKey => {
      const [dayIndex, timeIndex] = cellKey.split('-').map(Number);
      const day = this.config.days[dayIndex];
      const time = this.timeLabels[timeIndex];
      
      if (day && time) {
        changes.push({ day, time, value: null });
      }
    });

    if (changes.length > 0) {
      this.dispatchEvent(new CustomEvent('schedule-changed', {
        detail: { 
          mode: this.currentMode,
          changes 
        },
        bubbles: true,
        composed: true
      }));
    }

    this.showContextMenu = false;
  }

  private fillSelection() {
    if (this.selectedCells.size === 0) return;

    // Get the value from the first selected cell
    const firstSelectedKey = Array.from(this.selectedCells)[0];
    const [dayIndex, timeIndex] = firstSelectedKey.split('-').map(Number);
    const firstCell = this.gridCells[dayIndex]?.[timeIndex];
    
    if (!firstCell || firstCell.value === null) {
      this.showValueEditor = true;
      this.editorPosition = this.contextMenuPosition;
      this.editingValue = Math.round((this.minValue + this.maxValue) / 2);
    } else {
      const fillValue = firstCell.value;
      const changes: Array<{ day: string; time: string; value: number }> = [];
      
      this.selectedCells.forEach(cellKey => {
        const [dayIndex, timeIndex] = cellKey.split('-').map(Number);
        const day = this.config.days[dayIndex];
        const time = this.timeLabels[timeIndex];
        
        if (day && time) {
          changes.push({ day, time, value: fillValue });
        }
      });

      if (changes.length > 0) {
        this.dispatchEvent(new CustomEvent('schedule-changed', {
          detail: { 
            mode: this.currentMode,
            changes 
          },
          bubbles: true,
          composed: true
        }));
      }
    }

    this.showContextMenu = false;
  }

  private saveAsTemplate() {
    const templateName = prompt('Enter template name:');
    if (!templateName) return;

    const templateData = {
      mode: this.currentMode,
      cells: Array.from(this.selectedCells).map(cellKey => {
        const [dayIndex, timeIndex] = cellKey.split('-').map(Number);
        const day = this.config.days[dayIndex];
        const time = this.timeLabels[timeIndex];
        const cell = this.gridCells[dayIndex]?.[timeIndex];
        
        return {
          day,
          time,
          value: cell?.value || null,
          dayOffset: dayIndex,
          timeOffset: timeIndex
        };
      }).filter(cell => cell.value !== null)
    };

    this.templates.push({ name: templateName, data: templateData });
    
    // Save to localStorage
    localStorage.setItem('roost-scheduler-templates', JSON.stringify(this.templates));
    
    this.showContextMenu = false;
    
    this.dispatchEvent(new CustomEvent('show-message', {
      detail: { 
        message: `Template "${templateName}" saved`,
        type: 'success'
      },
      bubbles: true,
      composed: true
    }));
  }

  private loadTemplate(template: any) {
    if (!template.data || !template.data.cells) return;

    const changes: Array<{ day: string; time: string; value: number }> = [];
    
    // Get the first selected cell as the anchor point
    const firstSelectedKey = Array.from(this.selectedCells)[0];
    if (!firstSelectedKey) return;

    const [anchorDayIndex, anchorTimeIndex] = firstSelectedKey.split('-').map(Number);
    
    // Calculate the offset from the template's first cell
    const templateCells = template.data.cells;
    if (templateCells.length === 0) return;

    const firstTemplateCell = templateCells[0];
    const baseDayOffset = firstTemplateCell.dayOffset;
    const baseTimeOffset = firstTemplateCell.timeOffset;

    templateCells.forEach((templateCell: any) => {
      // Calculate relative position within the template
      const relativeDayOffset = templateCell.dayOffset - baseDayOffset;
      const relativeTimeOffset = templateCell.timeOffset - baseTimeOffset;
      
      // Apply to anchor position
      const targetDayIndex = anchorDayIndex + relativeDayOffset;
      const targetTimeIndex = anchorTimeIndex + relativeTimeOffset;
      
      // Check bounds
      if (targetDayIndex >= 0 && targetDayIndex < this.config.days.length &&
          targetTimeIndex >= 0 && targetTimeIndex < this.timeLabels.length) {
        
        const targetDay = this.config.days[targetDayIndex];
        const targetTime = this.timeLabels[targetTimeIndex];
        
        changes.push({ day: targetDay, time: targetTime, value: templateCell.value });
      }
    });

    if (changes.length > 0) {
      this.dispatchEvent(new CustomEvent('schedule-changed', {
        detail: { 
          mode: this.currentMode,
          changes 
        },
        bubbles: true,
        composed: true
      }));
    }

    this.showTemplateMenu = false;
    this.showContextMenu = false;
  }

  private deleteTemplate(templateIndex: number) {
    if (confirm(`Delete template "${this.templates[templateIndex].name}"?`)) {
      this.templates.splice(templateIndex, 1);
      localStorage.setItem('roost-scheduler-templates', JSON.stringify(this.templates));
      this.requestUpdate();
    }
  }

  private loadTemplatesFromStorage() {
    try {
      const stored = localStorage.getItem('roost-scheduler-templates');
      if (stored) {
        this.templates = JSON.parse(stored);
      }
    } catch (error) {
      console.warn('Failed to load templates from storage:', error);
      this.templates = [];
    }
  }

  private applyBulkOperation(operation: string, value?: number) {
    if (this.selectedCells.size === 0) return;

    const changes: Array<{ day: string; time: string; value: number }> = [];
    
    this.selectedCells.forEach(cellKey => {
      const [dayIndex, timeIndex] = cellKey.split('-').map(Number);
      const day = this.config.days[dayIndex];
      const time = this.timeLabels[timeIndex];
      const currentCell = this.gridCells[dayIndex]?.[timeIndex];
      
      if (day && time) {
        let newValue: number;
        
        switch (operation) {
          case 'add':
            newValue = (currentCell?.value || 0) + (value || 1);
            break;
          case 'subtract':
            newValue = (currentCell?.value || 0) - (value || 1);
            break;
          case 'multiply':
            newValue = (currentCell?.value || 0) * (value || 1);
            break;
          case 'set':
            newValue = value || 0;
            break;
          default:
            return;
        }
        
        // Clamp to valid range
        newValue = Math.max(this.minValue, Math.min(this.maxValue, newValue));
        changes.push({ day, time, value: newValue });
      }
    });

    if (changes.length > 0) {
      this.dispatchEvent(new CustomEvent('schedule-changed', {
        detail: { 
          mode: this.currentMode,
          changes 
        },
        bubbles: true,
        composed: true
      }));
    }

    this.showBulkEditor = false;
  }

  private validateValue(value: number): { isValid: boolean; message?: string } {
    if (isNaN(value)) {
      return { isValid: false, message: 'Please enter a valid number' };
    }
    
    if (value < this.minValue) {
      return { isValid: false, message: `Value must be at least ${this.minValue}°` };
    }
    
    if (value > this.maxValue) {
      return { isValid: false, message: `Value must be at most ${this.maxValue}°` };
    }
    
    return { isValid: true };
  }

  private handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      this.closeValueEditor();
    } else if (event.key === 'Enter') {
      this.applyValueToSelection();
    }
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

      .toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
      }

      .toolbar-actions {
        display: flex;
        gap: 8px;
      }

      .toolbar-button {
        padding: 6px 12px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        cursor: pointer;
        font-size: 0.9em;
        transition: all 0.2s ease;
      }

      .toolbar-button:hover:not(:disabled) {
        background: var(--secondary-background-color);
      }

      .toolbar-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
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

      .grid-cell.selected {
        box-shadow: inset 0 0 0 2px var(--primary-color);
        transform: scale(1.02);
        z-index: 2;
      }

      .grid-cell.selected.current-time {
        box-shadow: inset 0 0 0 3px var(--accent-color), inset 0 0 0 2px var(--primary-color);
      }

      @keyframes pulse {
        0%, 100% { box-shadow: inset 0 0 0 3px var(--accent-color); }
        50% { box-shadow: inset 0 0 0 3px transparent; }
      }

      /* Value Editor Styles */
      .value-editor-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .value-editor {
        position: absolute;
        background: var(--card-background-color);
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        min-width: 280px;
        max-width: 90vw;
        transform: translate(-50%, -50%);
        border: 1px solid var(--divider-color);
      }

      .editor-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        border-bottom: 1px solid var(--divider-color);
        font-weight: 500;
      }

      .close-btn {
        background: none;
        border: none;
        font-size: 20px;
        cursor: pointer;
        color: var(--secondary-text-color);
        padding: 0;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
      }

      .close-btn:hover {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
      }

      .editor-content {
        padding: 16px;
      }

      .value-input-group {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
      }

      .value-input {
        flex: 1;
        padding: 8px 12px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font-size: 16px;
      }

      .value-input:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 0 2px rgba(var(--primary-color-rgb), 0.2);
      }

      .unit {
        color: var(--secondary-text-color);
        font-weight: 500;
      }

      .range-info, .selection-info {
        font-size: 0.9em;
        color: var(--secondary-text-color);
        margin-bottom: 8px;
      }

      .editor-actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 16px;
      }

      .cancel-btn, .apply-btn {
        padding: 8px 16px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s ease;
      }

      .cancel-btn {
        background: var(--card-background-color);
        color: var(--secondary-text-color);
      }

      .cancel-btn:hover {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
      }

      .apply-btn {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-color: var(--primary-color);
      }

      .apply-btn:hover:not(:disabled) {
        background: var(--primary-color);
        opacity: 0.9;
      }

      .apply-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
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

      /* Context Menu Styles */
      .context-menu {
        position: fixed;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        z-index: 1001;
        min-width: 160px;
        padding: 4px 0;
      }

      .context-menu-item {
        display: block;
        width: 100%;
        padding: 8px 16px;
        border: none;
        background: none;
        color: var(--primary-text-color);
        text-align: left;
        cursor: pointer;
        font-size: 0.9em;
        transition: background-color 0.2s ease;
      }

      .context-menu-item:hover:not(:disabled) {
        background: var(--secondary-background-color);
      }

      .context-menu-item:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .context-menu-separator {
        margin: 4px 0;
        border: none;
        border-top: 1px solid var(--divider-color);
      }

      /* Modal Styles */
      .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
      }

      .bulk-editor, .template-menu {
        background: var(--card-background-color);
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        max-width: 500px;
        width: 100%;
        max-height: 80vh;
        overflow-y: auto;
        border: 1px solid var(--divider-color);
      }

      .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        border-bottom: 1px solid var(--divider-color);
      }

      .modal-header h3 {
        margin: 0;
        font-size: 1.1em;
        font-weight: 500;
      }

      /* Bulk Editor Styles */
      .bulk-editor-content {
        padding: 16px;
      }

      .bulk-operation {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
      }

      .bulk-operation label {
        min-width: 100px;
        font-size: 0.9em;
        color: var(--secondary-text-color);
      }

      .input-group {
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .input-group input {
        padding: 6px 8px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        width: 80px;
      }

      .input-group button {
        padding: 6px 12px;
        border: 1px solid var(--primary-color);
        border-radius: 4px;
        background: var(--primary-color);
        color: var(--text-primary-color);
        cursor: pointer;
        font-size: 0.9em;
      }

      .input-group button:hover {
        opacity: 0.9;
      }

      /* Template Menu Styles */
      .template-list {
        padding: 16px;
        max-height: 400px;
        overflow-y: auto;
      }

      .empty-templates {
        text-align: center;
        color: var(--secondary-text-color);
        padding: 32px 16px;
      }

      .empty-templates p {
        margin: 8px 0;
      }

      .template-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        margin-bottom: 8px;
        background: var(--secondary-background-color);
      }

      .template-info {
        flex: 1;
      }

      .template-name {
        display: block;
        font-weight: 500;
        margin-bottom: 4px;
      }

      .template-details {
        font-size: 0.8em;
        color: var(--secondary-text-color);
      }

      .template-actions {
        display: flex;
        gap: 8px;
      }

      .template-action-btn {
        padding: 4px 8px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.8em;
        transition: all 0.2s ease;
      }

      .template-action-btn.apply-btn {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-color: var(--primary-color);
      }

      .template-action-btn.apply-btn:hover:not(:disabled) {
        opacity: 0.9;
      }

      .template-action-btn.apply-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .template-action-btn.delete-btn {
        background: var(--error-color, #f44336);
        color: white;
        border-color: var(--error-color, #f44336);
      }

      .template-action-btn.delete-btn:hover {
        opacity: 0.9;
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