import { IsNotEmpty, IsUUID } from 'class-validator';

export class CloseCircleDto {
  @IsUUID('4')
  @IsNotEmpty()
  circleId: string;
}
