/**
 * Tests for advanced grid features: copy/paste, bulk edit, and templates
 */
import { expect } from '@esm-bundle/chai';
import { fixture, html } from '@open-wc/testing';
import { ScheduleGridComponent } from './grid-component';
import { ScheduleGrid } from './types';

describe('Advanced Grid Features', () => {
  let element: ScheduleGridComponent;
  let mockScheduleData: ScheduleGrid;

  beforeEach(async () => {
    mockScheduleData = {
      home: {
        monday: [
          { start_time: '06:00', end_time: '08:00', target_value: 20 },
          { start_time: '08:00', end_time: '18:00', target_value: 18 },
          { start_time: '18:00', end_time: '22:00', target_value: 21 }
        ],
        tuesday: [
          { start_time: '07:00', end_time: '09:00', target_value: 19 }
        ]
      },
      away: {
        monday: [
          { start_time: '00:00', end_time: '23:59', target_value: 16 }
        ]
      }
    };

    element = await fixture(html`
      <schedule-grid
        .scheduleData=${mockScheduleData}
        .currentMode=${'home'}
        .config=${{
          resolution_minutes: 30,
          start_hour: 0,
          end_hour: 24,
          days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        }}
        .minValue=${10}
        .maxValue=${30}
      ></schedule-grid>
    `);

    // Wait for the component to initialize
    await element.updateComplete;
  });

  describe('Copy/Paste Functionality', () => {
    it('should copy selected cells', () => {
      // Select some cells
      element['selectedCells'].add('0-12'); // Monday 6:00
      element['selectedCells'].add('0-13'); // Monday 6:30
      
      // Trigger copy
      element['copySelection']();
      
      expect(element['copiedCells']).to.have.length(2);
      expect(element['copiedCells'][0]).to.deep.include({
        day: 'monday',
        time: '06:00',
        value: 20
      });
    });

    it('should paste cells to new location', () => {
      // Set up copied cells
      element['copiedCells'] = [
        { day: 'monday', time: '06:00', value: 20 },
        { day: 'monday', time: '06:30', value: 20 }
      ];

      // Select target location (Tuesday)
      element['selectedCells'].add('1-14'); // Tuesday 7:00

      let eventFired = false;
      let eventDetail: any;

      element.addEventListener('schedule-changed', (e: any) => {
        eventFired = true;
        eventDetail = e.detail;
      });

      // Trigger paste
      element['pasteSelection']();

      expect(eventFired).to.be.true;
      expect(eventDetail.changes).to.have.length(2);
      expect(eventDetail.changes[0]).to.deep.include({
        day: 'tuesday',
        time: '07:00',
        value: 20
      });
    });

    it('should handle keyboard shortcuts', () => {
      // Select cells
      element['selectedCells'].add('0-12');
      
      // Mock copy method
      let copyCalled = false;
      element['copySelection'] = () => { copyCalled = true; };

      // Simulate Ctrl+C
      const event = new KeyboardEvent('keydown', {
        key: 'c',
        ctrlKey: true
      });

      element['handleGlobalKeyDown'](event);
      expect(copyCalled).to.be.true;
    });

    it('should clear selection with Delete key', () => {
      element['selectedCells'].add('0-12');
      
      let eventFired = false;
      element.addEventListener('schedule-changed', () => {
        eventFired = true;
      });

      const event = new KeyboardEvent('keydown', { key: 'Delete' });
      element['handleGlobalKeyDown'](event);

      expect(eventFired).to.be.true;
    });
  });

  describe('Bulk Edit Operations', () => {
    beforeEach(() => {
      // Select multiple cells
      element['selectedCells'].add('0-12'); // Monday 6:00
      element['selectedCells'].add('0-13'); // Monday 6:30
      element['selectedCells'].add('1-14'); // Tuesday 7:00
    });

    it('should set all selected cells to a value', () => {
      let eventFired = false;
      let eventDetail: any;

      element.addEventListener('schedule-changed', (e: any) => {
        eventFired = true;
        eventDetail = e.detail;
      });

      element['applyBulkOperation']('set', 22);

      expect(eventFired).to.be.true;
      expect(eventDetail.changes).to.have.length(3);
      expect(eventDetail.changes.every((change: any) => change.value === 22)).to.be.true;
    });

    it('should add value to all selected cells', () => {
      let eventDetail: any;
      element.addEventListener('schedule-changed', (e: any) => {
        eventDetail = e.detail;
      });

      element['applyBulkOperation']('add', 2);

      expect(eventDetail.changes).to.have.length(3);
      // Values should be increased by 2 from their current values
      expect(eventDetail.changes[0].value).to.equal(22); // 20 + 2
    });

    it('should subtract value from all selected cells', () => {
      let eventDetail: any;
      element.addEventListener('schedule-changed', (e: any) => {
        eventDetail = e.detail;
      });

      element['applyBulkOperation']('subtract', 3);

      expect(eventDetail.changes).to.have.length(3);
      expect(eventDetail.changes[0].value).to.equal(17); // 20 - 3
    });

    it('should clamp values to valid range', () => {
      let eventDetail: any;
      element.addEventListener('schedule-changed', (e: any) => {
        eventDetail = e.detail;
      });

      // Try to set value above maximum
      element['applyBulkOperation']('set', 35);

      expect(eventDetail.changes.every((change: any) => change.value === 30)).to.be.true;
    });
  });

  describe('Template Functionality', () => {
    beforeEach(() => {
      // Clear localStorage
      localStorage.removeItem('roost-scheduler-templates');
      element['templates'] = [];
    });

    it('should save selection as template', () => {
      // Select cells
      element['selectedCells'].add('0-12');
      element['selectedCells'].add('0-13');

      // Mock prompt to return template name
      const originalPrompt = window.prompt;
      window.prompt = () => 'Test Template';

      let eventFired = false;
      element.addEventListener('show-message', () => {
        eventFired = true;
      });

      element['saveAsTemplate']();

      expect(element['templates']).to.have.length(1);
      expect(element['templates'][0].name).to.equal('Test Template');
      expect(eventFired).to.be.true;

      // Restore original prompt
      window.prompt = originalPrompt;
    });

    it('should load template to selected area', () => {
      const template = {
        name: 'Test Template',
        data: {
          mode: 'home',
          cells: [
            { day: 'monday', time: '06:00', value: 22, dayOffset: 0, timeOffset: 12 },
            { day: 'monday', time: '06:30', value: 22, dayOffset: 0, timeOffset: 13 }
          ]
        }
      };

      // Select target area
      element['selectedCells'].add('1-14'); // Tuesday 7:00

      let eventFired = false;
      let eventDetail: any;

      element.addEventListener('schedule-changed', (e: any) => {
        eventFired = true;
        eventDetail = e.detail;
      });

      element['loadTemplate'](template);

      expect(eventFired).to.be.true;
      expect(eventDetail.changes).to.have.length(2);
      expect(eventDetail.changes[0]).to.deep.include({
        day: 'tuesday',
        time: '07:00',
        value: 22
      });
    });

    it('should delete template', () => {
      element['templates'] = [
        { name: 'Template 1', data: {} },
        { name: 'Template 2', data: {} }
      ];

      // Mock confirm to return true
      const originalConfirm = window.confirm;
      window.confirm = () => true;

      element['deleteTemplate'](0);

      expect(element['templates']).to.have.length(1);
      expect(element['templates'][0].name).to.equal('Template 2');

      // Restore original confirm
      window.confirm = originalConfirm;
    });

    it('should load templates from localStorage', () => {
      const templates = [
        { name: 'Saved Template', data: { cells: [] } }
      ];

      localStorage.setItem('roost-scheduler-templates', JSON.stringify(templates));

      element['loadTemplatesFromStorage']();

      expect(element['templates']).to.have.length(1);
      expect(element['templates'][0].name).to.equal('Saved Template');
    });

    it('should handle corrupted localStorage gracefully', () => {
      localStorage.setItem('roost-scheduler-templates', 'invalid json');

      element['loadTemplatesFromStorage']();

      expect(element['templates']).to.have.length(0);
    });
  });

  describe('Fill Selection', () => {
    it('should fill selection with first cell value', () => {
      // Select multiple cells
      element['selectedCells'].add('0-12'); // Monday 6:00 (value: 20)
      element['selectedCells'].add('0-13'); // Monday 6:30
      element['selectedCells'].add('1-14'); // Tuesday 7:00

      let eventFired = false;
      let eventDetail: any;

      element.addEventListener('schedule-changed', (e: any) => {
        eventFired = true;
        eventDetail = e.detail;
      });

      element['fillSelection']();

      expect(eventFired).to.be.true;
      expect(eventDetail.changes).to.have.length(3);
      expect(eventDetail.changes.every((change: any) => change.value === 20)).to.be.true;
    });

    it('should show value editor if first cell is empty', () => {
      // Select cells where first cell has no value
      element['selectedCells'].add('2-12'); // Wednesday (no schedule)

      element['fillSelection']();

      expect(element['showValueEditor']).to.be.true;
    });
  });

  describe('Context Menu', () => {
    it('should show context menu on right click', () => {
      const event = new MouseEvent('contextmenu', {
        clientX: 100,
        clientY: 200
      });

      element['handleCellRightClick'](event, 0, 12);

      expect(element['showContextMenu']).to.be.true;
      expect(element['contextMenuPosition']).to.deep.equal({ x: 100, y: 200 });
      expect(element['selectedCells'].has('0-12')).to.be.true;
    });

    it('should close context menu on global click', () => {
      element['showContextMenu'] = true;

      const event = new MouseEvent('click');
      Object.defineProperty(event, 'target', {
        value: document.createElement('div')
      });

      element['handleGlobalClick'](event);

      expect(element['showContextMenu']).to.be.false;
    });
  });

  describe('UI State Management', () => {
    it('should enable/disable toolbar buttons based on selection', async () => {
      // No selection - bulk edit should be disabled
      element['selectedCells'].clear();
      await element.updateComplete;

      const bulkEditBtn = element.shadowRoot?.querySelector('.toolbar-button') as HTMLButtonElement;
      expect(bulkEditBtn?.disabled).to.be.true;

      // With selection - bulk edit should be enabled
      element['selectedCells'].add('0-12');
      await element.updateComplete;

      expect(bulkEditBtn?.disabled).to.be.false;
    });

    it('should show/hide modals correctly', async () => {
      element['showBulkEditor'] = true;
      await element.updateComplete;

      const bulkEditor = element.shadowRoot?.querySelector('.bulk-editor');
      expect(bulkEditor).to.exist;

      element['showBulkEditor'] = false;
      await element.updateComplete;

      const hiddenBulkEditor = element.shadowRoot?.querySelector('.bulk-editor');
      expect(hiddenBulkEditor).to.not.exist;
    });
  });

  describe('Keyboard Shortcuts', () => {
    it('should ignore shortcuts when typing in input fields', () => {
      const input = document.createElement('input');
      const event = new KeyboardEvent('keydown', {
        key: 'c',
        ctrlKey: true
      });
      Object.defineProperty(event, 'target', { value: input });

      let copyCalled = false;
      element['copySelection'] = () => { copyCalled = true; };

      element['handleGlobalKeyDown'](event);
      expect(copyCalled).to.be.false;
    });

    it('should handle Escape key to close modals', () => {
      element['showContextMenu'] = true;
      element['showTemplateMenu'] = true;
      element['showBulkEditor'] = true;
      element['selectedCells'].add('0-12');

      const event = new KeyboardEvent('keydown', { key: 'Escape' });
      element['handleGlobalKeyDown'](event);

      expect(element['showContextMenu']).to.be.false;
      expect(element['showTemplateMenu']).to.be.false;
      expect(element['showBulkEditor']).to.be.false;
      expect(element['selectedCells'].size).to.equal(0);
    });
  });

  describe('Error Handling', () => {
    it('should handle invalid template data gracefully', () => {
      const invalidTemplate = {
        name: 'Invalid Template',
        data: null
      };

      element['selectedCells'].add('0-12');

      let eventFired = false;
      element.addEventListener('schedule-changed', () => {
        eventFired = true;
      });

      element['loadTemplate'](invalidTemplate);

      expect(eventFired).to.be.false;
    });

    it('should handle paste with no copied cells', () => {
      element['copiedCells'] = [];
      element['selectedCells'].add('0-12');

      let eventFired = false;
      element.addEventListener('schedule-changed', () => {
        eventFired = true;
      });

      element['pasteSelection']();

      expect(eventFired).to.be.false;
    });
  });
});