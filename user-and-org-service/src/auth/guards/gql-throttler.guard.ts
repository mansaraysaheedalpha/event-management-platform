// src/auth/guards/gql-throttler.guard.ts
import { ThrottlerGuard } from '@nestjs/throttler';
import { Injectable } from '@nestjs/common';
import { GqlExecutionContext } from '@nestjs/graphql';

@Injectable()
export class GqlThrottlerGuard extends ThrottlerGuard {
  getRequestResponse(context: GqlExecutionContext) {
    const gqlCtx = GqlExecutionContext.create(context);
    const { req } = gqlCtx.getContext() as { req: Request & { res: Response } };
    return { req, res: req.res };
  }
}
