import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class CreateCircleDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  topic: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
