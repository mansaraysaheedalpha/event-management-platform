//src/auth/gql_types/auth.inputs.ts
import { InputType, Field } from '@nestjs/graphql';
import {
  IsEmail,
  IsNotEmpty,
  IsString,
  MinLength,
  Length,
} from 'class-validator';

@InputType()
export class LoginInput {
  @Field()
  @IsEmail()
  email: string;

  @Field()
  @IsString()
  password: string;
}

@InputType()
export class RegisterUserInput {
  @Field()
  @IsString()
  @IsNotEmpty()
  organization_name: string;

  @Field()
  @IsString()
  @IsNotEmpty()
  first_name: string;

  @Field()
  @IsString()
  @IsNotEmpty()
  last_name: string;

  @Field()
  @IsEmail()
  email: string;

  @Field()
  @MinLength(8)
  password: string;
}

@InputType()
export class Login2FAInput {
  @Field()
  @IsString()
  userId: string;

  @Field()
  @IsString()
  @Length(6, 6)
  code: string;
}

@InputType()
export class RequestResetInput {
  @Field()
  @IsEmail()
  email: string;
}

@InputType()
export class PerformResetInput {
  @Field()
  @IsString()
  resetToken: string;

  @Field()
  @MinLength(8)
  newPassword: string;
}
