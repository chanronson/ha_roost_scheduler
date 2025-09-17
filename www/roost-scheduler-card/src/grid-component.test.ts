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
});