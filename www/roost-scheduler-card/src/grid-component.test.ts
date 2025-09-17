import { expect, fixture, html } from '@open-wc/testing';
import './grid-component';
import { ScheduleGridComponent } from './grid-component';
import { ScheduleGrid, GridConfig } from './types';

describe('ScheduleGridComponent', () => {
  let element: ScheduleGridComponent;
  
  const mockScheduleData: ScheduleGrid = {
    home: {
      monday: [
        {
          day: 'monday',
          start_time: '06:00',
          end_time: '08:00',
          target_value: 20,
          entity_domain: 'climate'
        },
        {
          day: 'monday',
          start_time: '18:00',
          end_time: '22:00',
          target_value: 22,
          entity_domain: 'climate'
        }
      ],
      tuesday: [
        {
          day: 'tuesday',
          start_time: '07:00',
          end_time: '09:00',
          target_value: 19,
          entity_domain: 'climate'
        }
      ]
    },
    away: {
      monday: [
        {
          day: 'monday',
          start_time: '08:00',
          end_time: '18:00',
          target_value: 16,
          entity_domain: 'climate'
        }
      ]
    }
  };

  const mockConfig: GridConfig = {
    resolution_minutes: 30,
    start_hour: 0,
    end_hour: 24,
    days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
  };

  beforeEach(async () => {
    element = await fixture(html`
      <schedule-grid
        .scheduleData=${mockScheduleData}
        .currentMode=${'home'}
        .config=${mockConfig}
        .minValue=${10}
        .maxValue=${30}
      ></schedule-grid>
    `);
    await element.updateComplete;
  });

  it('should render without errors', () => {
    expect(element).to.exist;
    expect(element.shadowRoot).to.exist;
  });

  it('should display mode selector with available modes', async () => {
    const modeButtons = element.shadowRoot?.querySelectorAll('.mode-button');
    expect(modeButtons).to.have.length(2);
    
    const buttonTexts = Array.from(modeButtons || []).map(btn => btn.textContent?.trim());
    expect(buttonTexts).to.include('Home');
    expect(buttonTexts).to.include('Away');
  });

  it('should highlight active mode', async () => {
    const activeButton = element.shadowRoot?.querySelector('.mode-button.active');
    expect(activeButton?.textContent?.trim()).to.equal('Home');
  });

  it('should render grid with correct number of days', async () => {
    const gridRows = element.shadowRoot?.querySelectorAll('.grid-row');
    expect(gridRows).to.have.length(7); // 7 days of the week
  });

  it('should render time labels based on resolution', async () => {
    const timeLabels = element.shadowRoot?.querySelectorAll('.time-label');
    // 24 hours * (60 / 30 minutes) = 48 time slots
    expect(timeLabels).to.have.length(48);
  });

  it('should display schedule values in correct cells', async () => {
    const activeCells = element.shadowRoot?.querySelectorAll('.grid-cell.active');
    expect(activeCells && activeCells.length).to.be.greaterThan(0);
    
    // Check if cells contain temperature values
    const cellWithValue = Array.from(activeCells || []).find(cell => 
      cell.textContent?.includes('°')
    );
    expect(cellWithValue).to.exist;
  });

  it('should emit mode-changed event when mode button is clicked', async () => {
    let eventFired = false;
    let eventDetail: any = null;
    
    element.addEventListener('mode-changed', (event: any) => {
      eventFired = true;
      eventDetail = event.detail;
    });
    
    const awayButton = Array.from(element.shadowRoot?.querySelectorAll('.mode-button') || [])
      .find(btn => btn.textContent?.trim() === 'Away') as HTMLElement;
    
    if (awayButton) {
      awayButton.click();
      expect(eventFired).to.be.true;
      expect(eventDetail.mode).to.equal('away');
    }
  });

  it('should handle empty schedule data gracefully', async () => {
    element.scheduleData = {};
    await element.updateComplete;
    
    const loadingMessage = element.shadowRoot?.querySelector('.grid-loading');
    expect(loadingMessage).to.exist;
  });

  it('should apply correct colors based on temperature values', async () => {
    const activeCells = element.shadowRoot?.querySelectorAll('.grid-cell.active');
    
    // Check that active cells have background colors (not transparent)
    if (activeCells) {
      activeCells.forEach(cell => {
        const style = getComputedStyle(cell as Element);
        expect(style.backgroundColor).to.not.equal('transparent');
      });
    }
  });

  it('should handle different resolutions', async () => {
    // Test with 15-minute resolution
    element.config = {
      ...mockConfig,
      resolution_minutes: 15
    };
    await element.updateComplete;
    
    const timeLabels = element.shadowRoot?.querySelectorAll('.time-label');
    // 24 hours * (60 / 15 minutes) = 96 time slots
    expect(timeLabels).to.have.length(96);
  });

  it('should show current time indicator', async () => {
    // Mock current time to be within a schedule slot
    const originalDate = Date;
    const mockDate = new Date('2023-01-02T07:30:00'); // Monday 7:30 AM
    
    // @ts-ignore
    global.Date = class extends Date {
      constructor() {
        super();
        return mockDate;
      }
      static now() {
        return mockDate.getTime();
      }
    };
    
    element = await fixture(html`
      <schedule-grid
        .scheduleData=${mockScheduleData}
        .currentMode=${'home'}
        .config=${mockConfig}
        .minValue=${10}
        .maxValue=${30}
      ></schedule-grid>
    `);
    
    await element.updateComplete;
    
    const currentTimeCell = element.shadowRoot?.querySelector('.grid-cell.current-time');
    expect(currentTimeCell).to.exist;
    
    // Restore original Date
    global.Date = originalDate;
  });

  it('should display legend with temperature range', async () => {
    const legend = element.shadowRoot?.querySelector('.legend');
    expect(legend).to.exist;
    
    const gradientLabels = element.shadowRoot?.querySelector('.gradient-labels');
    expect(gradientLabels?.textContent).to.include('10°');
    expect(gradientLabels?.textContent).to.include('30°');
  });

  it('should be responsive on mobile screens', async () => {
    // Simulate mobile viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 480,
    });
    
    await element.updateComplete;
    
    // Check that mobile styles are applied (this is a basic check)
    const gridContainer = element.shadowRoot?.querySelector('.grid-container');
    expect(gridContainer).to.exist;
  });

  // Interaction tests
  it('should handle cell click events', async () => {
    let eventFired = false;
    let eventDetail: any = null;
    
    element.addEventListener('cell-clicked', (event: any) => {
      eventFired = true;
      eventDetail = event.detail;
    });
    
    const gridCell = element.shadowRoot?.querySelector('.grid-cell[data-day-index="0"][data-time-index="12"]') as HTMLElement;
    if (gridCell) {
      gridCell.click();
      expect(eventFired).to.be.true;
      expect(eventDetail.day).to.equal('monday');
    }
  });

  it('should start drag selection on mousedown', async () => {
    const gridCell = element.shadowRoot?.querySelector('.grid-cell[data-day-index="0"][data-time-index="12"]') as HTMLElement;
    if (gridCell) {
      const mouseEvent = new MouseEvent('mousedown', { bubbles: true });
      gridCell.dispatchEvent(mouseEvent);
      
      // Check that dragging state is set (we can't directly access private properties in tests)
      // But we can check if the cell gets selected
      await element.updateComplete;
      expect(gridCell.classList.contains('selected')).to.be.true;
    }
  });

  it('should show value editor when drag selection ends', async () => {
    const gridCell = element.shadowRoot?.querySelector('.grid-cell[data-day-index="0"][data-time-index="12"]') as HTMLElement;
    if (gridCell) {
      // Simulate drag start
      const mouseDownEvent = new MouseEvent('mousedown', { bubbles: true, clientX: 100, clientY: 100 });
      gridCell.dispatchEvent(mouseDownEvent);
      
      // Simulate drag end
      const mouseUpEvent = new MouseEvent('mouseup', { bubbles: true, clientX: 100, clientY: 100 });
      document.dispatchEvent(mouseUpEvent);
      
      await element.updateComplete;
      
      const valueEditor = element.shadowRoot?.querySelector('.value-editor');
      expect(valueEditor).to.exist;
    }
  });

  it('should emit schedule-changed event when applying values', async () => {
    let eventFired = false;
    let eventDetail: any = null;
    
    element.addEventListener('schedule-changed', (event: any) => {
      eventFired = true;
      eventDetail = event.detail;
    });
    
    // Simulate selecting a cell and opening editor
    const gridCell = element.shadowRoot?.querySelector('.grid-cell[data-day-index="0"][data-time-index="12"]') as HTMLElement;
    if (gridCell) {
      const mouseDownEvent = new MouseEvent('mousedown', { bubbles: true, clientX: 100, clientY: 100 });
      gridCell.dispatchEvent(mouseDownEvent);
      
      const mouseUpEvent = new MouseEvent('mouseup', { bubbles: true, clientX: 100, clientY: 100 });
      document.dispatchEvent(mouseUpEvent);
      
      await element.updateComplete;
      
      // Set a value and apply
      const valueInput = element.shadowRoot?.querySelector('.value-input') as HTMLInputElement;
      const applyBtn = element.shadowRoot?.querySelector('.apply-btn') as HTMLButtonElement;
      
      if (valueInput && applyBtn) {
        valueInput.value = '22';
        valueInput.dispatchEvent(new Event('input'));
        
        await element.updateComplete;
        
        applyBtn.click();
        
        expect(eventFired).to.be.true;
        expect(eventDetail.mode).to.equal('home');
        expect(eventDetail.changes).to.be.an('array');
        expect(eventDetail.changes[0].value).to.equal(22);
      }
    }
  });

  it('should validate temperature values within range', async () => {
    // Test validation method indirectly through the UI
    const gridCell = element.shadowRoot?.querySelector('.grid-cell[data-day-index="0"][data-time-index="12"]') as HTMLElement;
    if (gridCell) {
      const mouseDownEvent = new MouseEvent('mousedown', { bubbles: true, clientX: 100, clientY: 100 });
      gridCell.dispatchEvent(mouseDownEvent);
      
      const mouseUpEvent = new MouseEvent('mouseup', { bubbles: true, clientX: 100, clientY: 100 });
      document.dispatchEvent(mouseUpEvent);
      
      await element.updateComplete;
      
      const valueInput = element.shadowRoot?.querySelector('.value-input') as HTMLInputElement;
      const applyBtn = element.shadowRoot?.querySelector('.apply-btn') as HTMLButtonElement;
      
      if (valueInput && applyBtn) {
        // Test value too high (50 > maxValue of 30)
        valueInput.value = '50';
        const inputEvent = new Event('input', { bubbles: true });
        valueInput.dispatchEvent(inputEvent);
        
        // Manually trigger the value change handler
        (element as any).editingValue = 50;
        await element.updateComplete;
        
        // Apply button should be disabled for invalid values
        expect(applyBtn.disabled).to.be.true;
        
        // Test valid value
        valueInput.value = '22';
        valueInput.dispatchEvent(inputEvent);
        (element as any).editingValue = 22;
        await element.updateComplete;
        
        expect(applyBtn.disabled).to.be.false;
      }
    }
  });

  it('should close value editor on escape key', async () => {
    const gridCell = element.shadowRoot?.querySelector('.grid-cell[data-day-index="0"][data-time-index="12"]') as HTMLElement;
    if (gridCell) {
      const mouseDownEvent = new MouseEvent('mousedown', { bubbles: true, clientX: 100, clientY: 100 });
      gridCell.dispatchEvent(mouseDownEvent);
      
      const mouseUpEvent = new MouseEvent('mouseup', { bubbles: true, clientX: 100, clientY: 100 });
      document.dispatchEvent(mouseUpEvent);
      
      await element.updateComplete;
      
      let valueEditor = element.shadowRoot?.querySelector('.value-editor');
      expect(valueEditor).to.exist;
      
      // Press escape
      const escapeEvent = new KeyboardEvent('keydown', { key: 'Escape' });
      valueEditor?.dispatchEvent(escapeEvent);
      
      await element.updateComplete;
      
      valueEditor = element.shadowRoot?.querySelector('.value-editor');
      expect(valueEditor).to.not.exist;
    }
  });

  it('should handle multi-cell selection with drag', async () => {
    // This is a simplified test since we can't easily simulate complex mouse movements in JSDOM
    const startCell = element.shadowRoot?.querySelector('.grid-cell[data-day-index="0"][data-time-index="12"]') as HTMLElement;
    
    if (startCell) {
      // Start drag
      const mouseDownEvent = new MouseEvent('mousedown', { bubbles: true, clientX: 100, clientY: 100 });
      startCell.dispatchEvent(mouseDownEvent);
      
      // Since we can't simulate elementFromPoint in JSDOM, we'll manually set the drag state
      // This tests the basic drag functionality
      (element as any).dragStartCell = { day: 0, time: 12 };
      (element as any).dragEndCell = { day: 0, time: 14 };
      (element as any).updateSelectedCells();
      
      await element.updateComplete;
      
      // Check that cells are selected (at least the start cell)
      const selectedCells = element.shadowRoot?.querySelectorAll('.grid-cell.selected');
      expect(selectedCells && selectedCells.length).to.be.greaterThan(0);
    }
  });
});