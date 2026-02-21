// src/users/gql_types/user.types.ts (Corrected)

import { ObjectType, Field, ID, Directive } from '@nestjs/graphql';

@ObjectType('User')
@Directive('@key(fields: "id")')
export class GqlUser {
  @Field(() => ID)
  id: string;

  @Field()
  email: string;

  @Field()
  first_name: string;

  @Field()
  last_name: string;

  @Field(() => String, { nullable: true })
  imageUrl: string | null;

  @Field(() => Boolean)
  isTwoFactorEnabled: boolean;

  @Field(() => Boolean)
  isPlatformAdmin: boolean;

  @Field(() => String)
  userType: string;
}
