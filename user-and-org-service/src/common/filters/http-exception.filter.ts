// src/common/filters/http-exception.filter.ts

import {
  ExceptionFilter,
  Catch,
  HttpException,
  ArgumentsHost,
} from '@nestjs/common';
import { Request, Response } from 'express';

@Catch(HttpException)
export class HttpExceptionFilter implements ExceptionFilter {
  catch(exception: HttpException, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();

    const status = exception.getStatus();
    const errorResponse = exception.getResponse();

    const customErrorResponse = {
      statusCode: status,
      timestamp: new Date().toISOString(),
      path: request.url,
      method: request.method,
      message:
        typeof errorResponse === 'string'
          ? errorResponse
          : typeof errorResponse === 'object' &&
              errorResponse !== null &&
              'message' in errorResponse
            ? (errorResponse as { message: string | string[] }).message
            : errorResponse,
    };

    return response.status(status).json(customErrorResponse);
  }
}
