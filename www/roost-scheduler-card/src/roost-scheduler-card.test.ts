import { describe, it, expect, beforeEach } from 'vitest';
import { fixture, html } from '@open-wc/testing';
import './roost-scheduler-card';
import { RoostSchedulerCard } from './roost-scheduler-card';
import { RoostSchedulerCardConfig, HomeAssistant } from './types';

describe('RoostSchedulerCard', () => {
  let element: RoostSchedulerCard;
  let mockHass: HomeAssistant;

  beforeEach(async () => {
    mockHass = {
      states: {
        'climate.living_room': {
          entity_id: 'climate.living_room',
          state: 'heat',
          attributes: {
            friendly_name: 'Living Room Climate',
            temperature: 20,
            target_temp_high: 25,
            target_temp_low: 15,
          },
        },
      },
      callService: async () => ({}),
      callWS: async () => ({ schedules: {} }),
      connection: {},
      language: 'en',
      themes: {},
      user: {},
    } as any;

    element = await fixture(html`<roost-scheduler-card></roost-scheduler-card>`);
    element.hass = mockHass;
  });

  it('should create element', () => {
    expect(element).toBeInstanceOf(RoostSchedulerCard);
  });

  it('should throw error when no config provided', () => {
    expect(() => element.setConfig(null as any)).toThrow('Invalid configuration');
  });

  it('should throw error when no entity provided', () => {
    const config: RoostSchedulerCardConfig = {
      type: 'custom:roost-scheduler-card',
    };
    expect(() => element.setConfig(config)).toThrow('Entity is required');
  });

  it('should accept valid config', () => {
    const config: RoostSchedulerCardConfig = {
      type: 'custom:roost-scheduler-card',
      entity: 'climate.living_room',
      name: 'Test Card',
    };
    
    expect(() => element.setConfig(config)).not.toThrow();
  });

  it('should return correct card size', () => {
    const config: RoostSchedulerCardConfig = {
      type: 'custom:roost-scheduler-card',
      entity: 'climate.living_room',
    };
    element.setConfig(config);
    
    expect(element.getCardSize()).toBe(6);
  });

  it('should return stub config', () => {
    const stubConfig = RoostSchedulerCard.getStubConfig();
    
    expect(stubConfig).toEqual({
      type: 'custom:roost-scheduler-card',
      entity: '',
      name: 'Roost Scheduler',
      show_header: true,
      resolution_minutes: 30,
    });
  });

  it('should render error when entity not found', async () => {
    const config: RoostSchedulerCardConfig = {
      type: 'custom:roost-scheduler-card',
      entity: 'climate.nonexistent',
    };
    element.setConfig(config);
    await element.updateComplete;

    const errorElement = element.shadowRoot?.querySelector('.error');
    expect(errorElement?.textContent).toContain('Entity "climate.nonexistent" not found');
  });

  it('should render card with valid entity', async () => {
    const config: RoostSchedulerCardConfig = {
      type: 'custom:roost-scheduler-card',
      entity: 'climate.living_room',
      name: 'Test Card',
    };
    element.setConfig(config);
    await element.updateComplete;

    const cardHeader = element.shadowRoot?.querySelector('.card-header .name');
    expect(cardHeader?.textContent?.trim()).toBe('Test Card');
  });
});