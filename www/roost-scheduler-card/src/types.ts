// Home Assistant types - simplified for our use case

declare global {
  interface HTMLElementTagNameMap {
    'roost-scheduler-card': RoostSchedulerCard;
    'roost-scheduler-card-editor': RoostSchedulerCardEditor;
  }
}

export interface LovelaceCardConfig {
  type: string;
}

export interface RoostSchedulerCardConfig extends LovelaceCardConfig {
  type: 'custom:roost-scheduler-card';
  entity?: string;
  name?: string;
  show_header?: boolean;
  resolution_minutes?: number;
}

export interface LovelaceCard extends HTMLElement {
  hass?: HomeAssistant;
  setConfig(config: any): void;
  getCardSize?(): number;
}

export interface LovelaceCardEditor extends HTMLElement {
  hass?: HomeAssistant;
  setConfig(config: any): void;
}

export interface RoostSchedulerCard extends LovelaceCard {
  setConfig(config: RoostSchedulerCardConfig): void;
}

export interface RoostSchedulerCardEditor extends LovelaceCardEditor {
  setConfig(config: RoostSchedulerCardConfig): void;
}

export interface HomeAssistant {
  states: { [entity_id: string]: any };
  callService: (domain: string, service: string, serviceData?: any) => Promise<any>;
  callWS: (msg: any) => Promise<any>;
  connection: any;
  language: string;
  themes: any;
  user: any;
}

export interface ScheduleSlot {
  day: string;
  start_time: string;
  end_time: string;
  target_value: number;
  entity_domain: string;
  buffer_override?: {
    time_minutes: number;
    value_delta: number;
  };
}

export interface ScheduleGrid {
  [mode: string]: {
    [day: string]: ScheduleSlot[];
  };
}