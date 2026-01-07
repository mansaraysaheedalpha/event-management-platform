// src/users/users.resolver.ts
import {
  Resolver,
  Query,
  Mutation,
  Context,
  Args,
  ResolveReference,
} from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { GqlAuthGuard } from 'src/auth/guards/gql-auth.guard';
import { UsersService } from './users.service';
import { GqlUser } from './gql_types/user.types';
import {
  ChangePasswordInput,
  UpdateMyProfileInput,
} from './gql_types/user.inputs';

@Resolver(() => GqlUser)
export class UsersResolver {
  constructor(private usersService: UsersService) {}

  @Query(() => GqlUser)
  @UseGuards(GqlAuthGuard)
  async getMyProfile(@Context() context: { req: { user: { sub: string } } }) {
    return this.usersService.findOne(context.req.user.sub);
  }

  @Query(() => GqlUser, { name: 'user' })
  @UseGuards(GqlAuthGuard)
  async findUserById(@Args('id') id: string) {
    return this.usersService.findOne(id);
  }

  @Mutation(() => GqlUser)
  @UseGuards(GqlAuthGuard)
  async updateMyProfile(
    @Args('input') input: UpdateMyProfileInput,
    @Context() context: { req: { user: { sub: string } } },
  ) {
    return this.usersService.updateProfile(context.req.user.sub, input);
  }

  @Mutation(() => Boolean)
  @UseGuards(GqlAuthGuard)
  async changePassword(
    @Args('input') input: ChangePasswordInput,
    @Context() context: { req: { user: { sub: string } } },
  ) {
    await this.usersService.changePassword(
      context.req.user.sub,
      input.currentPassword,
      input.newPassword,
    );
    return true; // Return true on success
  }

  @ResolveReference()
  resolveReference(reference: {
    __typename: string;
    id: string;
  }): Promise<GqlUser> {
    // Federation reference resolution - no logging needed
    return this.usersService.findOne(reference.id);
  }
}
