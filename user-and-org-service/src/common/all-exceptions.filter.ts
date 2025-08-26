// src/common/filters/all-exceptions.filter.ts
import {
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus, // Import HttpStatus
} from '@nestjs/common';
import { GqlExceptionFilter, GqlArgumentsHost } from '@nestjs/graphql';
import { ApolloError } from 'apollo-server-express';

@Catch()
export class AllExceptionsFilter implements GqlExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost) {
    const gqlHost = GqlArgumentsHost.create(host);
    console.error('--- Global Exception Filter Caught ---', exception);

    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      const message = exception.message;

      // This is the key change: map HTTP statuses to semantic GraphQL error codes
      let code = 'INTERNAL_SERVER_ERROR';
      if (status === HttpStatus.UNAUTHORIZED) {
        code = 'UNAUTHORIZED';
      } else if (status === HttpStatus.FORBIDDEN) {
        code = 'FORBIDDEN';
      } else if (status === HttpStatus.NOT_FOUND) {
        code = 'NOT_FOUND';
      } else if (status === HttpStatus.BAD_REQUEST) {
        // <-- ADD THIS CASE
        code = 'BAD_REQUEST';
      }

      // You can add more mappings here as needed

      throw new ApolloError(message, code);
    }

    throw new ApolloError('Internal server error', 'INTERNAL_SERVER_ERROR');
  }
}
