// src/users/gql_types/user.inputs.ts
import { InputType, Field } from '@nestjs/graphql';
import { IsOptional, IsString, MinLength } from 'class-validator';

@InputType()
export class UpdateMyProfileInput {
  @Field(() => String, { nullable: true })
  @IsString()
  @IsOptional()
  first_name?: string;

  @Field(() => String, { nullable: true })
  @IsString()
  @IsOptional()
  last_name?: string;
}

@InputType()
export class ChangePasswordInput {
  @Field()
  @IsString()
  currentPassword: string;

  @Field()
  @IsString()
  @MinLength(8, { message: 'New password must be at least 8 characters long' })
  newPassword: string;
}
