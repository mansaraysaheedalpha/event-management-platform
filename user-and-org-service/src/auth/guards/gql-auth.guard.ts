// src/auth/guards/gql-auth.guard.ts
import {
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { GqlExecutionContext } from '@nestjs/graphql';
import { AuthGuard } from '@nestjs/passport';

@Injectable()
export class GqlAuthGuard extends AuthGuard('jwt') {
  getRequest(context: ExecutionContext) {
    const ctx = GqlExecutionContext.create(context);
    return ctx.getContext().req;
  }

  // This method provides better error handling for GraphQL
  handleRequest(err: any, user: any, info: any) {
    if (err || !user) {
      // Log the detailed error on the server for debugging
      console.error('GQL Auth Error:', info?.message || err?.message);
      throw (
        err || new UnauthorizedException('Could not authenticate with token')
      );
    }
    return user;
  }
}
