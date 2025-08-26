import { ObjectType, Field, ID } from '@nestjs/graphql';
import { GqlUser } from 'src/users/gql_types/user.types';

// This payload is for successful authentication results (e.g., after registration or 2FA)
@ObjectType()
export class AuthPayload {
  @Field()
  token: string;

  @Field(() => GqlUser)
  user: GqlUser;
}

// This new payload handles the initial login attempt, which might require a 2FA step
@ObjectType()
export class LoginPayload {
  @Field(() => String, { nullable: true })
  token?: string | null;

  @Field(() => GqlUser, { nullable: true })
  user?: GqlUser | null;

  @Field()
  requires2FA: boolean;

  @Field(() => ID, { nullable: true })
  userIdFor2FA?: string | null;

  // ADD THIS NEW FIELD
  @Field(() => String, { nullable: true })
  onboardingToken?: string;
}
