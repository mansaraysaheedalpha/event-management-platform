import { IsNotEmpty, IsUUID } from 'class-validator';

export class JoinCircleDto {
  @IsUUID('4')
  @IsNotEmpty()
  circleId: string;
}
