// src/two-factor/two-factor.resolver.ts
import { Resolver, Mutation, Context, Args } from '@nestjs/graphql';
import { TwoFactorService } from './two-factor.service';
import { UseGuards } from '@nestjs/common';
import { GqlAuthGuard } from 'src/auth/guards/gql-auth.guard';// It's better to create a GraphQL-specific auth guard
import { TwoFactorSetupPayload } from './gql_types/two_factor.types';
import { TurnOn2FAInput } from './gql_types/two-factor.inputs';

@Resolver()
export class TwoFactorResolver {
  constructor(private twoFactorService: TwoFactorService) {}

  @Mutation(() => TwoFactorSetupPayload)
  @UseGuards(GqlAuthGuard) // Protect this mutation
  async generate2FA(@Context() context: { req: { user: { sub: string } } }) {
    const userId = context.req.user.sub;
    return this.twoFactorService.setup2FA(userId);
  }

  @Mutation(() => String)
  @UseGuards(GqlAuthGuard) // Protect this mutation
  async turnOn2FA(
    @Context() context: { req: { user: { sub: string } } },
    @Args('input') turnOn2FAInput: TurnOn2FAInput,
  ): Promise<string> {
    const userId = context.req.user.sub;
    const { message } = await this.twoFactorService.turnOn2FA(
      userId,
      turnOn2FAInput.code,
    );
    return message;
  }

  @Mutation(() => String)
  @UseGuards(GqlAuthGuard)
  async turnOff2FA(
    @Context() context: { req: { user: { sub: string } } },
  ): Promise<string> {
    const userId = context.req.user.sub;
    const { message } = await this.twoFactorService.turnOff2FA(userId);
    return message;
  }
}
