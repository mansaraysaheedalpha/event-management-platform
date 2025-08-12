//src/networking/circles/dto/join-circle.dto.ts
import { IsNotEmpty, IsUUID } from 'class-validator';

export class JoinCircleDto {
  @IsUUID('4')
  @IsNotEmpty()
  circleId: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
