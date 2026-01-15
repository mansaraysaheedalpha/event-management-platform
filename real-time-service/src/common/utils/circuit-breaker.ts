// src/common/utils/circuit-breaker.ts
/**
 * Circuit breaker pattern for external API calls.
 * Prevents cascade failures when external services are down.
 */
import { Logger } from '@nestjs/common';

export enum CircuitState {
  CLOSED = 'closed', // Normal operation
  OPEN = 'open', // Failing, reject requests
  HALF_OPEN = 'half_open', // Testing if service recovered
}

export class CircuitBreakerOpenError extends Error {
  constructor(serviceName: string) {
    super(`Circuit breaker is open for service: ${serviceName}`);
    this.name = 'CircuitBreakerOpenError';
  }
}

export interface CircuitBreakerOptions {
  /** Service identifier */
  name: string;
  /** Number of failures before opening circuit (default: 5) */
  failMax?: number;
  /** Seconds before attempting to close circuit (default: 30) */
  resetTimeout?: number;
  /** Timeout for individual calls in ms (default: 10000) */
  callTimeout?: number;
  /** Exception types that don't count as failures */
  excludeExceptions?: Array<new (...args: any[]) => Error>;
}

export interface CircuitBreakerStats {
  name: string;
  state: CircuitState;
  failureCount: number;
  failMax: number;
  resetTimeout: number;
  lastFailureTime: string | null;
  successCount: number;
  totalCalls: number;
}

export class CircuitBreaker {
  private readonly logger = new Logger(CircuitBreaker.name);
  private readonly name: string;
  private readonly failMax: number;
  private readonly resetTimeout: number;
  private readonly callTimeout: number;
  private readonly excludeExceptions: Array<new (...args: any[]) => Error>;

  private state: CircuitState = CircuitState.CLOSED;
  private failureCount = 0;
  private successCount = 0;
  private totalCalls = 0;
  private lastFailureTime: Date | null = null;

  constructor(options: CircuitBreakerOptions) {
    this.name = options.name;
    this.failMax = options.failMax ?? 5;
    this.resetTimeout = options.resetTimeout ?? 30;
    this.callTimeout = options.callTimeout ?? 10000;
    this.excludeExceptions = options.excludeExceptions ?? [];
  }

  /**
   * Execute a function through the circuit breaker.
   */
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    this.totalCalls++;

    // Check if circuit allows the call
    this.beforeCall();

    try {
      // Execute with timeout
      const result = await this.withTimeout(fn(), this.callTimeout);
      this.onSuccess();
      return result;
    } catch (error) {
      if (!this.isExcludedException(error)) {
        this.onFailure(error as Error);
      }
      throw error;
    }
  }

  /**
   * Execute with a timeout wrapper.
   */
  private async withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
    let timeoutHandle: ReturnType<typeof setTimeout>;

    const timeoutPromise = new Promise<never>((_, reject) => {
      timeoutHandle = setTimeout(() => {
        reject(new Error(`Circuit breaker ${this.name}: call timed out after ${timeoutMs}ms`));
      }, timeoutMs);
    });

    try {
      const result = await Promise.race([promise, timeoutPromise]);
      clearTimeout(timeoutHandle!);
      return result;
    } catch (error) {
      clearTimeout(timeoutHandle!);
      throw error;
    }
  }

  /**
   * Check circuit state before allowing call.
   */
  private beforeCall(): void {
    if (this.state === CircuitState.CLOSED) {
      return;
    }

    if (this.state === CircuitState.OPEN) {
      // Check if timeout has elapsed
      if (this.shouldAttemptReset()) {
        this.state = CircuitState.HALF_OPEN;
        this.logger.log(`Circuit breaker ${this.name} entering HALF_OPEN state`);
        return;
      }
      throw new CircuitBreakerOpenError(this.name);
    }

    // HALF_OPEN - allow the call to test recovery
  }

  /**
   * Handle successful call.
   */
  private onSuccess(): void {
    this.successCount++;

    if (this.state === CircuitState.HALF_OPEN) {
      // Service recovered, close circuit
      this.reset();
      this.logger.log(`Circuit breaker ${this.name} recovered, closing circuit`);
    } else if (this.state === CircuitState.CLOSED) {
      // Reset failure count on success
      this.failureCount = 0;
    }
  }

  /**
   * Handle failed call.
   */
  private onFailure(error: Error): void {
    this.failureCount++;
    this.lastFailureTime = new Date();

    this.logger.warn(
      `Circuit breaker ${this.name} failure ${this.failureCount}/${this.failMax}: ${error.message}`,
    );

    if (this.state === CircuitState.HALF_OPEN) {
      // Failed during recovery test, reopen
      this.state = CircuitState.OPEN;
      this.logger.warn(`Circuit breaker ${this.name} reopened after failed recovery`);
    } else if (this.state === CircuitState.CLOSED) {
      if (this.failureCount >= this.failMax) {
        this.state = CircuitState.OPEN;
        this.logger.warn(
          `Circuit breaker ${this.name} opened after ${this.failureCount} failures`,
        );
      }
    }
  }

  /**
   * Check if enough time has passed to attempt recovery.
   */
  private shouldAttemptReset(): boolean {
    if (!this.lastFailureTime) {
      return true;
    }
    const elapsed = (Date.now() - this.lastFailureTime.getTime()) / 1000;
    return elapsed >= this.resetTimeout;
  }

  /**
   * Reset circuit to closed state.
   */
  private reset(): void {
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.lastFailureTime = null;
  }

  /**
   * Check if exception type should be excluded from failure tracking.
   */
  private isExcludedException(error: unknown): boolean {
    if (!(error instanceof Error)) return false;
    return this.excludeExceptions.some((ExcludedType) => error instanceof ExcludedType);
  }

  /**
   * Get circuit breaker statistics.
   */
  getStats(): CircuitBreakerStats {
    return {
      name: this.name,
      state: this.state,
      failureCount: this.failureCount,
      failMax: this.failMax,
      resetTimeout: this.resetTimeout,
      lastFailureTime: this.lastFailureTime?.toISOString() ?? null,
      successCount: this.successCount,
      totalCalls: this.totalCalls,
    };
  }

  /**
   * Check if circuit is closed (normal operation).
   */
  isClosed(): boolean {
    return this.state === CircuitState.CLOSED;
  }

  /**
   * Check if circuit is open (failing).
   */
  isOpen(): boolean {
    return this.state === CircuitState.OPEN;
  }

  /**
   * Get current state.
   */
  getState(): CircuitState {
    return this.state;
  }
}

// ===========================================
// Circuit Breaker Registry
// ===========================================

const circuitBreakers: Map<string, CircuitBreaker> = new Map();

/**
 * Get or create a circuit breaker by name.
 * Circuit breakers are reused across calls to maintain state.
 */
export function getCircuitBreaker(options: CircuitBreakerOptions): CircuitBreaker {
  const existing = circuitBreakers.get(options.name);
  if (existing) {
    return existing;
  }

  const breaker = new CircuitBreaker(options);
  circuitBreakers.set(options.name, breaker);
  return breaker;
}

/**
 * Get circuit breaker for LinkedIn API.
 */
export function getLinkedInBreaker(): CircuitBreaker {
  return getCircuitBreaker({
    name: 'linkedin',
    failMax: 3,
    resetTimeout: 60, // 1 minute
    callTimeout: 15000, // 15 seconds
  });
}

/**
 * Get circuit breaker for Oracle AI Service.
 */
export function getOracleAIBreaker(): CircuitBreaker {
  return getCircuitBreaker({
    name: 'oracle-ai',
    failMax: 5,
    resetTimeout: 30, // 30 seconds
    callTimeout: 30000, // 30 seconds (AI calls can be slow)
  });
}

/**
 * Get stats for all circuit breakers.
 */
export function getAllBreakerStats(): CircuitBreakerStats[] {
  return Array.from(circuitBreakers.values()).map((breaker) => breaker.getStats());
}

/**
 * Reset all circuit breakers (useful for testing).
 */
export function resetAllBreakers(): void {
  circuitBreakers.clear();
}
