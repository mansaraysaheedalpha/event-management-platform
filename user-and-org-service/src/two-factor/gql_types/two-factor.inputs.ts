import { InputType, Field } from '@nestjs/graphql';
import { IsString, Length } from 'class-validator';

@InputType()
export class TurnOn2FAInput {
  @Field()
  @IsString()
  @Length(6, 6)
  code: string;
}
