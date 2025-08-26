// src/users/gql_types/user.types.ts

import { ObjectType, Field, ID } from '@nestjs/graphql';

@ObjectType()
export class GqlUser {
  @Field(() => ID)
  id: string;

  @Field()
  email: string;

  @Field()
  first_name: string;

  @Field()
  last_name: string;

  @Field(() => String, { nullable: true }) // <-- More explicit and tells GraphQL it's a String
  imageUrl: string | null; // <-- This is the key change to allow null

  @Field(() => Boolean)
  isTwoFactorEnabled: boolean;
}
