// src/organizations/gql_types/organization.inputs.ts
import { InputType, Field, ID } from '@nestjs/graphql';
import {
  IsBoolean,
  IsEmail,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
} from 'class-validator';

@InputType()
export class CreateInvitationInput {
  @Field()
  @IsEmail()
  email: string;

  @Field()
  @IsString()
  @IsNotEmpty()
  role: string; // e.g., "MEMBER" or "ADMIN"
}

@InputType()
export class UpdateMemberRoleInput {
  @Field(() => ID)
  @IsUUID()
  memberId: string;

  @Field(() => ID)
  @IsUUID()
  roleId: string;
}

@InputType()
export class DeleteOrganizationInput {
  @Field(() => ID)
  @IsString() // <-- 2. Use IsString()
  @IsNotEmpty()
  organizationId: string;

  @Field(() => Boolean, { nullable: true })
  @IsBoolean()
  @IsOptional()
  force?: boolean;
}

// src/organizations/gql_types/organization.inputs.ts

// ADD THIS NEW CLASS
@InputType()
export class OnboardingCreateOrganizationInput {
  @Field()
  @IsString()
  @IsNotEmpty()
  name: string;
}

@InputType()
export class UpdateOrganizationInput {
  @Field(() => ID)
  @IsString() // <-- Change to this
  @IsNotEmpty() // <-- Add this
  organizationId: string;

  @Field()
  @IsString()
  @IsNotEmpty()
  name: string;
}
