//src/networking/circles/dto/close-circle.dto.ts
import { IsNotEmpty, IsUUID } from 'class-validator';

export class CloseCircleDto {
  @IsUUID('4')
  @IsNotEmpty()
  circleId: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
