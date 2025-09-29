import { LitElement, html, css, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { HomeAssistant, RoostSchedulerCardConfig, ScheduleGrid, GridConfig } from './types';
import { WebSocketManager, ConnectionStatus, WebSocketEvent } from './websocket-manager';
import './grid-component';

// Card version info for Home Assistant
const CARD_VERSION = '0.3.0';

// Enhanced card registration with comprehensive error handling and verification
class CardRegistrationManager {
  private static readonly CARD_TYPE = 'roost-scheduler-card';
  private static readonly CARD_NAME = 'Roost Scheduler Card';
  private static readonly MAX_RETRY_ATTEMPTS = 5;
  private static readonly INITIAL_RETRY_DELAY_MS = 500;
  private static readonly MAX_RETRY_DELAY_MS = 5000;
  private static readonly REGISTRATION_TIMEOUT_MS = 10000;
  
  private static registrationAttempts = 0;
  private static registrationSuccess = false;
  private static lastError: string | null = null;
  private static registrationPromise: Promise<boolean> | null = null;
  private static registrationStartTime: number = 0;

  static async registerCard(): Promise<boolean> {
    // Prevent multiple concurrent registration attempts
    if (this.registrationPromise) {
      console.log('[RoostSchedulerCard] Registration already in progress, waiting for completion');
      return this.registrationPromise;
    }

    // If already successfully registered, return immediately
    if (this.registrationSuccess && this.verifyRegistration()) {
      console.log('[RoostSchedulerCard] Card already successfully registered');
      return true;
    }

    // Start new registration process
    this.registrationPromise = this.performRegistration();
    
    try {
      const result = await this.registrationPromise;
      return result;
    } finally {
      this.registrationPromise = null;
    }
  }

  private static async performRegistration(): Promise<boolean> {
    this.registrationStartTime = Date.now();
    
    while (this.registrationAttempts < this.MAX_RETRY_ATTEMPTS) {
      // Check for timeout
      if (Date.now() - this.registrationStartTime > this.REGISTRATION_TIMEOUT_MS) {
        console.error('[RoostSchedulerCard] Registration timeout exceeded');
        this.lastError = 'Registration timeout exceeded';
        return false;
      }

      this.registrationAttempts++;
      
      try {
        console.log(`[RoostSchedulerCard] Registration attempt ${this.registrationAttempts}/${this.MAX_RETRY_ATTEMPTS} for ${this.CARD_TYPE}`);
        
        // Verify Home Assistant environment with enhanced checks
        const envCheck = await this.verifyHomeAssistantEnvironment();
        if (!envCheck.isValid) {
          throw new Error(`Home Assistant environment check failed: ${envCheck.reason}`);
        }

        // Wait for DOM to be ready if needed
        await this.waitForDOMReady();

        // Initialize customCards array if needed
        if (!(window as any).customCards) {
          (window as any).customCards = [];
          console.log('[RoostSchedulerCard] Initialized customCards array');
        }
        
        // Check if card is already registered with enhanced verification
        const existingCard = this.findExistingRegistration();
        if (existingCard) {
          console.log(`[RoostSchedulerCard] Card ${this.CARD_TYPE} already registered, verifying...`);
          
          // Verify the existing registration is valid
          if (this.verifyExistingRegistration(existingCard)) {
            this.registrationSuccess = true;
            this.lastError = null;
            console.log('[RoostSchedulerCard] Existing registration verified successfully');
            return true;
          } else {
            console.warn('[RoostSchedulerCard] Existing registration is invalid, re-registering');
            this.removeExistingRegistration();
          }
        }

        // Register the card with enhanced metadata
        const cardInfo = this.createCardInfo();
        (window as any).customCards.push(cardInfo);
        
        // Enhanced verification with multiple checks
        const verificationResult = await this.performEnhancedVerification();
        if (!verificationResult.success) {
          throw new Error(`Registration verification failed: ${verificationResult.reason}`);
        }

        console.log(`[RoostSchedulerCard] Successfully registered ${this.CARD_TYPE} v${CARD_VERSION}`);
        this.registrationSuccess = true;
        this.lastError = null;
        
        // Dispatch enhanced registration event
        this.dispatchRegistrationEvent(true);
        
        // Store registration metadata for diagnostics
        this.storeRegistrationMetadata();
        
        return true;
        
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.lastError = errorMessage;
        
        console.error(`[RoostSchedulerCard] Registration attempt ${this.registrationAttempts} failed:`, errorMessage);
        
        // Log detailed error information
        this.logDetailedError(errorMessage);
        
        // Calculate exponential backoff delay
        const delay = Math.min(
          this.INITIAL_RETRY_DELAY_MS * Math.pow(2, this.registrationAttempts - 1),
          this.MAX_RETRY_DELAY_MS
        );
        
        // Don't retry if we've exceeded max attempts
        if (this.registrationAttempts >= this.MAX_RETRY_ATTEMPTS) {
          console.error(`[RoostSchedulerCard] Failed to register card after ${this.MAX_RETRY_ATTEMPTS} attempts`);
          this.dispatchRegistrationEvent(false, errorMessage);
          return false;
        }
        
        console.log(`[RoostSchedulerCard] Retrying registration in ${delay}ms... (attempt ${this.registrationAttempts + 1}/${this.MAX_RETRY_ATTEMPTS})`);
        
        // Wait before retry
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    return false;
  }

  private static async verifyHomeAssistantEnvironment(): Promise<{ isValid: boolean; reason?: string }> {
    try {
      // Check for window object
      if (typeof window === 'undefined') {
        return { isValid: false, reason: 'Window object not available' };
      }

      // Check for customElements support (required for custom cards)
      if (!window.customElements) {
        return { isValid: false, reason: 'CustomElements API not supported' };
      }

      // Check for Lit framework support
      if (typeof customElement === 'undefined') {
        console.warn('[RoostSchedulerCard] Lit framework decorators not available, but proceeding');
      }

      // Enhanced Home Assistant environment detection
      const haChecks = {
        hassConnection: !!(window as any).hassConnection,
        loadCardHelpers: !!(window as any).loadCardHelpers,
        homeAssistantElement: !!document.querySelector('home-assistant'),
        hacsElement: !!document.querySelector('hacs-frontend'),
        lovelaceElement: !!document.querySelector('hui-root'),
        customCards: Array.isArray((window as any).customCards),
      };

      const hasAnyHaIndicator = Object.values(haChecks).some(check => check);
      
      if (!hasAnyHaIndicator) {
        // Wait a bit for Home Assistant to initialize
        console.log('[RoostSchedulerCard] Home Assistant environment not detected, waiting for initialization...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Re-check after waiting
        const recheckHaElement = !!document.querySelector('home-assistant');
        const recheckCustomCards = Array.isArray((window as any).customCards);
        
        if (!recheckHaElement && !recheckCustomCards) {
          console.warn('[RoostSchedulerCard] Home Assistant environment still not detected, but proceeding with registration');
        }
      }

      // Check browser compatibility
      const browserChecks = {
        es6Support: typeof Symbol !== 'undefined',
        promiseSupport: typeof Promise !== 'undefined',
        fetchSupport: typeof fetch !== 'undefined',
        webComponentsSupport: 'customElements' in window,
      };

      const incompatibleFeatures = Object.entries(browserChecks)
        .filter(([, supported]) => !supported)
        .map(([feature]) => feature);

      if (incompatibleFeatures.length > 0) {
        return { 
          isValid: false, 
          reason: `Browser missing required features: ${incompatibleFeatures.join(', ')}` 
        };
      }

      console.log('[RoostSchedulerCard] Environment checks:', { haChecks, browserChecks });
      return { isValid: true };
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('[RoostSchedulerCard] Error verifying Home Assistant environment:', error);
      return { isValid: false, reason: `Environment verification error: ${errorMessage}` };
    }
  }

  private static async waitForDOMReady(): Promise<void> {
    if (document.readyState === 'complete') {
      return;
    }

    return new Promise((resolve) => {
      const checkReady = () => {
        if (document.readyState === 'complete') {
          resolve();
        } else {
          setTimeout(checkReady, 100);
        }
      };
      checkReady();
    });
  }

  private static findExistingRegistration(): any {
    const customCards = (window as any).customCards;
    if (!Array.isArray(customCards)) {
      return null;
    }

    return customCards.find((card: any) => 
      card && 
      (card.type === this.CARD_TYPE || 
       card.type === `custom:${this.CARD_TYPE}`)
    );
  }

  private static verifyExistingRegistration(existingCard: any): boolean {
    try {
      // Check required properties
      const requiredProps = ['type', 'name'];
      for (const prop of requiredProps) {
        if (!existingCard[prop]) {
          console.warn(`[RoostSchedulerCard] Existing registration missing property: ${prop}`);
          return false;
        }
      }

      // Verify type matches exactly
      if (existingCard.type !== this.CARD_TYPE && existingCard.type !== `custom:${this.CARD_TYPE}`) {
        console.warn(`[RoostSchedulerCard] Existing registration has incorrect type: ${existingCard.type}`);
        return false;
      }

      return true;
    } catch (error) {
      console.error('[RoostSchedulerCard] Error verifying existing registration:', error);
      return false;
    }
  }

  private static removeExistingRegistration(): void {
    try {
      const customCards = (window as any).customCards;
      if (!Array.isArray(customCards)) {
        return;
      }

      const index = customCards.findIndex((card: any) => 
        card && 
        (card.type === this.CARD_TYPE || 
         card.type === `custom:${this.CARD_TYPE}`)
      );

      if (index !== -1) {
        customCards.splice(index, 1);
        console.log('[RoostSchedulerCard] Removed invalid existing registration');
      }
    } catch (error) {
      console.error('[RoostSchedulerCard] Error removing existing registration:', error);
    }
  }

  private static createCardInfo(): any {
    return {
      type: this.CARD_TYPE,
      name: this.CARD_NAME,
      description: 'A card for managing climate schedules with presence-aware automation',
      preview: true,
      documentationURL: 'https://github.com/user/roost-scheduler',
      version: CARD_VERSION,
      // Enhanced metadata for better integration
      domain: 'roost_scheduler',
      category: 'climate',
      configurable: true,
      customElement: 'roost-scheduler-card',
      // Registration timestamp for diagnostics
      registeredAt: new Date().toISOString(),
      registrationAttempt: this.registrationAttempts,
    };
  }

  private static async performEnhancedVerification(): Promise<{ success: boolean; reason?: string }> {
    try {
      // Basic array check
      const customCards = (window as any).customCards;
      if (!Array.isArray(customCards)) {
        return { success: false, reason: 'customCards is not an array' };
      }

      // Find registered card
      const registeredCard = customCards.find((card: any) => 
        card && (card.type === this.CARD_TYPE || card.type === `custom:${this.CARD_TYPE}`)
      );
      
      if (!registeredCard) {
        return { success: false, reason: 'Card not found in customCards array after registration' };
      }

      // Verify required properties
      const requiredProps = ['type', 'name', 'description'];
      for (const prop of requiredProps) {
        if (!registeredCard[prop]) {
          return { success: false, reason: `Missing required property: ${prop}` };
        }
      }

      // Verify card type is correct
      if (registeredCard.type !== this.CARD_TYPE) {
        return { success: false, reason: `Incorrect card type: expected ${this.CARD_TYPE}, got ${registeredCard.type}` };
      }

      // Verify custom element is defined
      if (!customElements.get('roost-scheduler-card')) {
        console.warn('[RoostSchedulerCard] Custom element not yet defined, but registration is valid');
      }

      // Additional verification: check if card appears in potential card picker
      await this.verifyCardPickerAvailability();

      console.log('[RoostSchedulerCard] Enhanced verification passed');
      return { success: true };
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('[RoostSchedulerCard] Error in enhanced verification:', error);
      return { success: false, reason: `Verification error: ${errorMessage}` };
    }
  }

  private static async verifyCardPickerAvailability(): Promise<void> {
    try {
      // This is a best-effort check to see if the card would be available in the picker
      // We can't directly access the card picker, but we can check for common indicators
      
      // Check if Lovelace is available
      const lovelaceElement = document.querySelector('hui-root') || 
                             document.querySelector('ha-panel-lovelace');
      
      if (lovelaceElement) {
        console.log('[RoostSchedulerCard] Lovelace environment detected, card should be available in picker');
      } else {
        console.warn('[RoostSchedulerCard] Lovelace environment not detected, card picker availability uncertain');
      }

      // Check for card helpers (used by card picker)
      if ((window as any).loadCardHelpers) {
        try {
          const helpers = await (window as any).loadCardHelpers();
          if (helpers && typeof helpers.createCardElement === 'function') {
            console.log('[RoostSchedulerCard] Card helpers available, card picker should work');
          }
        } catch (error) {
          console.warn('[RoostSchedulerCard] Could not load card helpers:', error);
        }
      }
      
    } catch (error) {
      console.warn('[RoostSchedulerCard] Error verifying card picker availability:', error);
    }
  }

  private static verifyRegistration(): boolean {
    try {
      // For synchronous compatibility, we'll do a basic check
      const customCards = (window as any).customCards;
      if (!Array.isArray(customCards)) {
        return false;
      }

      const registeredCard = customCards.find((card: any) => card && card.type === this.CARD_TYPE);
      return !!registeredCard;
    } catch (error) {
      console.error('[RoostSchedulerCard] Error in basic verification:', error);
      return false;
    }
  }

  private static dispatchRegistrationEvent(success: boolean, error?: string): void {
    try {
      const eventDetail = {
        cardType: this.CARD_TYPE,
        version: CARD_VERSION,
        success,
        attempts: this.registrationAttempts,
        error,
        timestamp: new Date().toISOString(),
      };

      const eventName = success ? 'roost-scheduler-card-registered' : 'roost-scheduler-card-registration-failed';
      
      window.dispatchEvent(new CustomEvent(eventName, {
        detail: eventDetail,
        bubbles: true,
      }));

      console.log(`[RoostSchedulerCard] Dispatched ${eventName} event`, eventDetail);
    } catch (error) {
      console.error('[RoostSchedulerCard] Error dispatching registration event:', error);
    }
  }

  private static storeRegistrationMetadata(): void {
    try {
      const metadata = {
        cardType: this.CARD_TYPE,
        version: CARD_VERSION,
        registeredAt: new Date().toISOString(),
        attempts: this.registrationAttempts,
        success: this.registrationSuccess,
        environment: {
          userAgent: navigator.userAgent,
          hasCustomElements: !!window.customElements,
          hasCustomCards: Array.isArray((window as any).customCards),
          customCardsCount: Array.isArray((window as any).customCards) ? (window as any).customCards.length : 0,
          homeAssistantDetected: !!(window as any).hassConnection || 
                                !!(window as any).loadCardHelpers ||
                                !!document.querySelector('home-assistant'),
          lovelaceDetected: !!document.querySelector('hui-root') || 
                           !!document.querySelector('ha-panel-lovelace'),
        },
      };

      (window as any).roostSchedulerCardRegistrationMetadata = metadata;
      console.log('[RoostSchedulerCard] Stored registration metadata for diagnostics');
    } catch (error) {
      console.error('[RoostSchedulerCard] Error storing registration metadata:', error);
    }
  }

  private static logDetailedError(errorMessage: string): void {
    const diagnostics = {
      error: errorMessage,
      attempt: this.registrationAttempts,
      maxAttempts: this.MAX_RETRY_ATTEMPTS,
      timestamp: new Date().toISOString(),
      registrationStartTime: this.registrationStartTime,
      timeElapsed: Date.now() - this.registrationStartTime,
      environment: {
        userAgent: navigator.userAgent,
        documentReadyState: document.readyState,
        hasCustomElements: !!window.customElements,
        hasCustomCards: !!(window as any).customCards,
        customCardsLength: Array.isArray((window as any).customCards) ? (window as any).customCards.length : 'N/A',
        homeAssistantDetected: !!(window as any).hassConnection || 
                              !!(window as any).loadCardHelpers ||
                              !!document.querySelector('home-assistant'),
        lovelaceDetected: !!document.querySelector('hui-root') || 
                         !!document.querySelector('ha-panel-lovelace'),
        hacsDetected: !!document.querySelector('hacs-frontend'),
      },
      cardInfo: {
        version: CARD_VERSION,
        customElementDefined: !!customElements.get('roost-scheduler-card'),
      },
      browserSupport: {
        es6: typeof Symbol !== 'undefined',
        promises: typeof Promise !== 'undefined',
        fetch: typeof fetch !== 'undefined',
        webComponents: 'customElements' in window,
        modules: 'noModule' in HTMLScriptElement.prototype,
      },
    };

    console.error('[RoostSchedulerCard] Detailed error diagnostics:', diagnostics);
    
    // Store diagnostics for potential retrieval by integration
    (window as any).roostSchedulerCardDiagnostics = diagnostics;
    
    // Also store in session storage for persistence across page reloads
    try {
      sessionStorage.setItem('roost-scheduler-card-diagnostics', JSON.stringify(diagnostics));
    } catch (storageError) {
      console.warn('[RoostSchedulerCard] Could not store diagnostics in session storage:', storageError);
    }
  }

  static getRegistrationStatus(): { 
    success: boolean; 
    attempts: number; 
    lastError: string | null;
    isInProgress: boolean;
    timeElapsed: number;
    metadata?: any;
  } {
    return {
      success: this.registrationSuccess,
      attempts: this.registrationAttempts,
      lastError: this.lastError,
      isInProgress: !!this.registrationPromise,
      timeElapsed: this.registrationStartTime ? Date.now() - this.registrationStartTime : 0,
      metadata: (window as any).roostSchedulerCardRegistrationMetadata,
    };
  }

  static async waitForRegistration(timeoutMs: number = 10000): Promise<boolean> {
    // If already successful and verified, return immediately
    if (this.registrationSuccess && this.verifyRegistration()) {
      return true;
    }

    // If registration is in progress, wait for it
    if (this.registrationPromise) {
      try {
        return await Promise.race([
          this.registrationPromise,
          new Promise<boolean>((_, reject) => 
            setTimeout(() => reject(new Error('Registration timeout')), timeoutMs)
          )
        ]);
      } catch (error) {
        console.warn('[RoostSchedulerCard] Registration wait timeout or error:', error);
        return false;
      }
    }

    // Otherwise, start registration and wait
    try {
      const registrationPromise = this.registerCard();
      return await Promise.race([
        registrationPromise,
        new Promise<boolean>((_, reject) => 
          setTimeout(() => reject(new Error('Registration timeout')), timeoutMs)
        )
      ]);
    } catch (error) {
      console.warn('[RoostSchedulerCard] Registration timeout reached:', error);
      return false;
    }
  }

  static async forceReregistration(): Promise<boolean> {
    console.log('[RoostSchedulerCard] Forcing re-registration...');
    
    // Reset state
    this.registrationSuccess = false;
    this.registrationAttempts = 0;
    this.lastError = null;
    this.registrationPromise = null;
    
    // Remove existing registration
    this.removeExistingRegistration();
    
    // Attempt registration again
    return this.registerCard();
  }

  static getDiagnostics(): any {
    const stored = (window as any).roostSchedulerCardDiagnostics;
    const metadata = (window as any).roostSchedulerCardRegistrationMetadata;
    
    return {
      current: this.getRegistrationStatus(),
      lastError: stored,
      metadata,
      sessionDiagnostics: this.getSessionDiagnostics(),
    };
  }

  private static getSessionDiagnostics(): any {
    try {
      const stored = sessionStorage.getItem('roost-scheduler-card-diagnostics');
      return stored ? JSON.parse(stored) : null;
    } catch (error) {
      console.warn('[RoostSchedulerCard] Could not retrieve session diagnostics:', error);
      return null;
    }
  }
}

// Perform initial registration with enhanced error handling
CardRegistrationManager.registerCard().then((success) => {
  if (success) {
    console.log('[RoostSchedulerCard] Initial card registration completed successfully');
  } else {
    console.error('[RoostSchedulerCard] Initial card registration failed - card may not appear in dashboard picker');
    
    // Store failure information for diagnostics
    const diagnostics = CardRegistrationManager.getDiagnostics();
    console.error('[RoostSchedulerCard] Registration failure diagnostics:', diagnostics);
  }
}).catch((error) => {
  console.error('[RoostSchedulerCard] Unexpected error during initial registration:', error);
});

// Export registration manager for potential use by integration
(window as any).RoostSchedulerCardRegistration = CardRegistrationManager;

// Also export diagnostics function for troubleshooting
(window as any).getRoostSchedulerCardDiagnostics = () => CardRegistrationManager.getDiagnostics();

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

  public static getRegistrationInfo(): any {
    const manager = (window as any).RoostSchedulerCardRegistration;
    if (!manager) {
      return {
        success: false,
        attempts: 0,
        lastError: 'Registration manager not available',
        isInProgress: false,
        timeElapsed: 0,
      };
    }

    return manager.getRegistrationStatus();
  }

  public static getFullDiagnostics(): any {
    const manager = (window as any).RoostSchedulerCardRegistration;
    if (!manager) {
      return {
        error: 'Registration manager not available',
        timestamp: new Date().toISOString(),
      };
    }

    return manager.getDiagnostics();
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

  connectedCallback(): void {
    super.connectedCallback();
    
    // Verify card registration when connected to DOM
    this.verifyCardRegistration();
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
            ${this.renderRegistrationDiagnostics()}
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
            ${this.renderRegistrationDiagnostics()}
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

  private async verifyCardRegistration(): Promise<void> {
    try {
      const registrationManager = (window as any).RoostSchedulerCardRegistration;
      
      if (!registrationManager) {
        console.warn('[RoostSchedulerCard] Registration manager not available');
        this.handleRegistrationError('Registration manager not available');
        return;
      }

      const status = registrationManager.getRegistrationStatus();
      console.log('[RoostSchedulerCard] Current registration status:', status);
      
      if (!status.success) {
        if (status.isInProgress) {
          console.log('[RoostSchedulerCard] Registration in progress, waiting for completion...');
          
          // Wait for ongoing registration to complete
          const success = await registrationManager.waitForRegistration(15000);
          
          if (!success) {
            console.error('[RoostSchedulerCard] Registration did not complete successfully');
            this.handleRegistrationError('Registration timeout or failure during initialization');
            return;
          }
        } else {
          console.warn('[RoostSchedulerCard] Card registration not successful, attempting re-registration');
          
          // Attempt to re-register
          const success = await registrationManager.registerCard();
          
          if (!success) {
            console.error('[RoostSchedulerCard] Failed to re-register card');
            const diagnostics = registrationManager.getDiagnostics();
            console.error('[RoostSchedulerCard] Re-registration failure diagnostics:', diagnostics);
            
            this.handleRegistrationError(
              `Registration failed after ${status.attempts} attempts. Last error: ${status.lastError || 'Unknown error'}`
            );
            return;
          }
        }
      }

      // Verify registration is actually working
      const finalStatus = registrationManager.getRegistrationStatus();
      if (finalStatus.success) {
        console.log('[RoostSchedulerCard] Card registration verified successfully');
        
        // Clear any previous registration errors
        if (this.error?.includes('Card registration')) {
          this.error = null;
        }
      } else {
        this.handleRegistrationError('Registration verification failed');
      }
      
    } catch (error) {
      console.error('[RoostSchedulerCard] Error verifying card registration:', error);
      this.handleRegistrationError(`Registration verification error: ${error}`);
    }
  }

  private handleRegistrationError(errorMessage: string): void {
    console.error('[RoostSchedulerCard] Registration error:', errorMessage);
    
    // Set error state to inform user, but make it dismissible
    this.error = `Card registration issue: ${errorMessage}. The card may not appear in the dashboard picker. Click to dismiss.`;
    
    // Make error clickable to dismiss
    this.addEventListener('click', this.dismissRegistrationError.bind(this), { once: true });
    
    // Auto-clear error after delay to not permanently block the UI
    setTimeout(() => {
      if (this.error?.includes('Card registration issue')) {
        this.error = null;
      }
    }, 15000);
  }

  private dismissRegistrationError(): void {
    if (this.error?.includes('Card registration issue')) {
      this.error = null;
      console.log('[RoostSchedulerCard] Registration error dismissed by user');
    }
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

  private renderRegistrationDiagnostics() {
    const registrationInfo = RoostSchedulerCard.getRegistrationInfo();
    
    // Only show diagnostics if there are registration issues
    if (registrationInfo.success) {
      return '';
    }

    const fullDiagnostics = RoostSchedulerCard.getFullDiagnostics();

    return html`
      <div class="registration-diagnostics">
        <details>
          <summary>Card Registration Diagnostics</summary>
          <div class="diagnostics-content">
            <div class="diagnostics-section">
              <h4>Registration Status</h4>
              <p><strong>Status:</strong> ${registrationInfo.success ? 'Success' : 'Failed'}</p>
              <p><strong>Attempts:</strong> ${registrationInfo.attempts}</p>
              <p><strong>In Progress:</strong> ${registrationInfo.isInProgress ? 'Yes' : 'No'}</p>
              ${registrationInfo.timeElapsed > 0 ? html`
                <p><strong>Time Elapsed:</strong> ${Math.round(registrationInfo.timeElapsed / 1000)}s</p>
              ` : ''}
              ${registrationInfo.lastError ? html`
                <p><strong>Last Error:</strong> ${registrationInfo.lastError}</p>
              ` : ''}
            </div>

            <div class="diagnostics-section">
              <h4>Environment</h4>
              <p><strong>Card Version:</strong> ${CARD_VERSION}</p>
              <p><strong>Custom Element Defined:</strong> ${customElements.get('roost-scheduler-card') ? 'Yes' : 'No'}</p>
              <p><strong>Custom Cards Array:</strong> ${Array.isArray((window as any).customCards) ? `${(window as any).customCards.length} cards` : 'Not available'}</p>
            </div>

            ${fullDiagnostics.lastError ? html`
              <div class="diagnostics-section">
                <h4>Last Error Details</h4>
                <p><strong>Error:</strong> ${fullDiagnostics.lastError.error}</p>
                <p><strong>Timestamp:</strong> ${new Date(fullDiagnostics.lastError.timestamp).toLocaleString()}</p>
                ${fullDiagnostics.lastError.environment?.homeAssistantDetected !== undefined ? html`
                  <p><strong>Home Assistant Detected:</strong> ${fullDiagnostics.lastError.environment.homeAssistantDetected ? 'Yes' : 'No'}</p>
                ` : ''}
              </div>
            ` : ''}

            <div class="diagnostics-actions">
              <button @click=${this.retryRegistration} class="retry-button">
                Retry Registration
              </button>
              <button @click=${this.copyDiagnostics} class="copy-button">
                Copy Full Diagnostics
              </button>
            </div>

            <div class="diagnostics-help">
              <p><em>If the card doesn't appear in the dashboard picker:</em></p>
              <ul>
                <li>Try clicking "Retry Registration" above</li>
                <li>Refresh the page (Ctrl+F5 or Cmd+Shift+R)</li>
                <li>Clear browser cache and reload</li>
                <li>Restart Home Assistant</li>
                <li>Check browser console for additional errors</li>
              </ul>
            </div>
          </div>
        </details>
      </div>
    `;
  }

  private async retryRegistration(): Promise<void> {
    try {
      console.log('[RoostSchedulerCard] User requested registration retry');
      
      const manager = (window as any).RoostSchedulerCardRegistration;
      if (!manager) {
        console.error('[RoostSchedulerCard] Registration manager not available for retry');
        return;
      }

      // Show loading state
      this.error = 'Retrying card registration...';
      
      // Force re-registration
      const success = await manager.forceReregistration();
      
      if (success) {
        console.log('[RoostSchedulerCard] Registration retry successful');
        this.error = 'Registration retry successful! The card should now appear in the dashboard picker.';
        
        // Clear success message after delay
        setTimeout(() => {
          if (this.error?.includes('Registration retry successful')) {
            this.error = null;
          }
        }, 5000);
      } else {
        console.error('[RoostSchedulerCard] Registration retry failed');
        const diagnostics = manager.getDiagnostics();
        console.error('[RoostSchedulerCard] Retry failure diagnostics:', diagnostics);
        
        this.error = 'Registration retry failed. Please check the diagnostics below and try the suggested solutions.';
      }
      
      // Force re-render to update diagnostics
      this.requestUpdate();
      
    } catch (error) {
      console.error('[RoostSchedulerCard] Error during registration retry:', error);
      this.error = `Registration retry error: ${error}`;
    }
  }

  private async copyDiagnostics(): Promise<void> {
    try {
      const diagnostics = RoostSchedulerCard.getFullDiagnostics();
      const diagnosticsText = JSON.stringify(diagnostics, null, 2);
      
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(diagnosticsText);
        console.log('[RoostSchedulerCard] Diagnostics copied to clipboard');
        
        // Show temporary success message
        const originalError = this.error;
        this.error = 'Diagnostics copied to clipboard!';
        
        setTimeout(() => {
          this.error = originalError;
        }, 2000);
      } else {
        // Fallback for browsers without clipboard API
        console.log('[RoostSchedulerCard] Full diagnostics:', diagnosticsText);
        alert('Diagnostics logged to console. Please copy from there.');
      }
    } catch (error) {
      console.error('[RoostSchedulerCard] Error copying diagnostics:', error);
      alert('Failed to copy diagnostics. Please check the browser console.');
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

      .registration-diagnostics {
        margin-top: 16px;
        padding: 12px;
        background: var(--warning-color);
        background-opacity: 0.1;
        border-radius: 4px;
        border-left: 4px solid var(--warning-color);
      }

      .registration-diagnostics summary {
        cursor: pointer;
        font-weight: 500;
        color: var(--warning-color);
        margin-bottom: 8px;
      }

      .registration-diagnostics summary:hover {
        text-decoration: underline;
      }

      .diagnostics-content {
        margin-top: 8px;
        font-size: 0.9em;
        color: var(--secondary-text-color);
      }

      .diagnostics-section {
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--divider-color);
      }

      .diagnostics-section:last-of-type {
        border-bottom: none;
        margin-bottom: 0;
      }

      .diagnostics-section h4 {
        margin: 0 0 8px 0;
        font-size: 1em;
        font-weight: 600;
        color: var(--primary-text-color);
      }

      .diagnostics-content p {
        margin: 4px 0;
      }

      .diagnostics-content ul {
        margin: 8px 0;
        padding-left: 20px;
      }

      .diagnostics-content li {
        margin: 4px 0;
      }

      .diagnostics-content em {
        font-style: italic;
        color: var(--primary-text-color);
      }

      .diagnostics-actions {
        margin: 16px 0;
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .retry-button, .copy-button {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.9em;
        font-weight: 500;
        transition: background-color 0.2s ease;
      }

      .retry-button {
        background: var(--primary-color);
        color: var(--text-primary-color);
      }

      .retry-button:hover {
        background: var(--primary-color);
        opacity: 0.8;
      }

      .copy-button {
        background: var(--secondary-color, #666);
        color: white;
      }

      .copy-button:hover {
        background: var(--secondary-color, #666);
        opacity: 0.8;
      }

      .diagnostics-help {
        margin-top: 16px;
        padding-top: 12px;
        border-top: 1px solid var(--divider-color);
      }

      .diagnostics-help p {
        font-weight: 500;
        margin-bottom: 8px;
      }
    `;
  }
}