// src/auth/guards/gql-throttler.guard.ts
import { ThrottlerGuard } from '@nestjs/throttler';
import { Injectable, ExecutionContext } from '@nestjs/common';
import { GqlExecutionContext } from '@nestjs/graphql';
import { Request, Response } from 'express';

@Injectable()
export class GqlThrottlerGuard extends ThrottlerGuard {
  getRequestResponse(context: ExecutionContext): { req: Request; res: Response } {
    // Check if this is a GraphQL request
    const contextType = context.getType<string>();

    if (contextType === 'graphql') {
      const gqlCtx = GqlExecutionContext.create(context);
      const ctx = gqlCtx.getContext<{ req: Request; res: Response }>();
      return { req: ctx.req, res: ctx.res };
    }

    // For HTTP requests (REST endpoints)
    const httpCtx = context.switchToHttp();
    return {
      req: httpCtx.getRequest<Request>(),
      res: httpCtx.getResponse<Response>(),
    };
  }

  // Override getTracker to handle cases where req.ip might be undefined
  protected async getTracker(req: Request): Promise<string> {
    // Try multiple ways to get the client IP
    const ip = req.ip ||
               req.headers['x-forwarded-for']?.toString().split(',')[0] ||
               req.socket?.remoteAddress ||
               'unknown';
    return ip;
  }
}
