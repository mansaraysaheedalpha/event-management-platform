// src/organizations/gql_types/organization.types.ts
import {
  ObjectType,
  Field,
  ID,
  registerEnumType,
  Directive,
} from '@nestjs/graphql';
import { GqlUser } from 'src/users/gql_types/user.types';
import { OrganizationStatus } from '@prisma/client';

// This tells GraphQL about our enum so it can be used in the schema
registerEnumType(OrganizationStatus, {
  name: 'OrganizationStatus',
});

@ObjectType('Organization')
@Directive('@key(fields: "id")')
export class Organization {
  @Field(() => ID)
  id: string;

  @Field()
  name: string;

  // --- ADD THESE NEW FIELDS ---
  @Field(() => OrganizationStatus)
  status: OrganizationStatus;

  @Field(() => Date, { nullable: true })
  deletionScheduledAt: Date | null;
  // ---------------------------
}

@ObjectType('Role')
@Directive('@key(fields: "id")')
export class Role {
  @Field(() => ID)
  id: string;

  @Field()
  name: string;
}

@ObjectType()
export class OrganizationMember {
  @Field(() => GqlUser)
  user: GqlUser;

  @Field(() => Role)
  role: Role;
}

@ObjectType()
export class DeleteOrganizationPayload {
  @Field()
  success: boolean;

  @Field(() => ID, { nullable: true })
  nextOrganizationId?: string | null;
}
