// src/common/filters/all-exceptions.filter.ts
import {
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
  ExceptionFilter,
} from '@nestjs/common';
import { GqlArgumentsHost, GqlContextType } from '@nestjs/graphql';
import { ApolloError } from 'apollo-server-express';
import { Response } from 'express';

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  // Messages that are safe to expose to clients
  private readonly SAFE_MESSAGE_PATTERNS = [
    /^Invalid credentials$/i,
    /^User not found/i,
    /^Organization not found/i,
    /^You do not have permission/i,
    /^Access denied/i,
    /^Forbidden/i,
    /^Unauthorized/i,
    /^Invalid.*token/i,
    /^Password must/i,
    /^Email already exists/i,
    /^CSRF validation failed$/i,
    /^Too many requests/i,
    /^Validation failed/i,
  ];

  private isSafeMessage(message: string): boolean {
    return this.SAFE_MESSAGE_PATTERNS.some((pattern) => pattern.test(message));
  }

  private sanitizeMessage(message: string, status: number): string {
    // Allow known safe messages through
    if (this.isSafeMessage(message)) {
      return message;
    }

    // For client errors (4xx), provide more context but avoid internals
    if (status >= 400 && status < 500) {
      // Check if it's a validation error with field info
      if (
        message.includes('must be') ||
        message.includes('must contain') ||
        message.includes('should be') ||
        message.includes('is not valid') ||
        message.includes('too short') ||
        message.includes('too long') ||
        message.includes('at least')
      ) {
        return message;
      }
      return 'Request could not be processed';
    }

    // For server errors, always return generic message
    return 'An unexpected error occurred';
  }

  catch(exception: unknown, host: ArgumentsHost) {
    // Log full error for debugging (never exposed to client)
    this.logger.error('Exception caught', {
      exception: exception instanceof Error ? {
        name: exception.name,
        message: exception.message,
        stack: exception.stack,
      } : exception,
    });

    // Determine if this is a GraphQL or HTTP request
    const contextType = host.getType<GqlContextType>();

    if (contextType === 'graphql') {
      // Handle GraphQL requests
      return this.handleGraphQLException(exception, host);
    } else {
      // Handle HTTP/REST requests
      return this.handleHttpException(exception, host);
    }
  }

  private handleHttpException(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let message = 'An unexpected error occurred';

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      let rawMessage = exception.message;

      // Handle ValidationPipe errors
      const exceptionResponse = exception.getResponse();
      if (typeof exceptionResponse === 'object' && exceptionResponse !== null) {
        const responseObj = exceptionResponse as Record<string, unknown>;
        if (Array.isArray(responseObj.message)) {
          rawMessage = responseObj.message.join(', ');
        } else if (typeof responseObj.message === 'string') {
          rawMessage = responseObj.message;
        }
      }

      message = this.sanitizeMessage(rawMessage, status);
    }

    response.status(status).json({
      statusCode: status,
      message: message,
      timestamp: new Date().toISOString(),
    });
  }

  private handleGraphQLException(exception: unknown, host: ArgumentsHost) {
    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      let rawMessage = exception.message;

      // Handle ValidationPipe errors - extract actual validation messages
      const response = exception.getResponse();
      if (typeof response === 'object' && response !== null) {
        const responseObj = response as Record<string, unknown>;
        if (Array.isArray(responseObj.message)) {
          rawMessage = responseObj.message.join(', ');
        } else if (typeof responseObj.message === 'string') {
          rawMessage = responseObj.message;
        }
      }

      // Map HTTP statuses to semantic GraphQL error codes
      let code = 'INTERNAL_SERVER_ERROR';
      if (status === HttpStatus.UNAUTHORIZED) {
        code = 'UNAUTHORIZED';
      } else if (status === HttpStatus.FORBIDDEN) {
        code = 'FORBIDDEN';
      } else if (status === HttpStatus.NOT_FOUND) {
        code = 'NOT_FOUND';
      } else if (status === HttpStatus.BAD_REQUEST) {
        code = 'BAD_REQUEST';
      } else if (status === HttpStatus.TOO_MANY_REQUESTS) {
        code = 'TOO_MANY_REQUESTS';
      } else if (status === HttpStatus.CONFLICT) {
        code = 'CONFLICT';
      }

      // Sanitize the message before exposing to client
      const safeMessage = this.sanitizeMessage(rawMessage, status);

      throw new ApolloError(safeMessage, code);
    }

    // For unknown exceptions, never expose internal details
    throw new ApolloError('An unexpected error occurred', 'INTERNAL_SERVER_ERROR');
  }
}
