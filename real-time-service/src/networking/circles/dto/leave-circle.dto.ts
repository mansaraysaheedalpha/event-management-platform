import { IsNotEmpty, IsUUID } from 'class-validator';

export class LeaveCircleDto {
  @IsUUID('4')
  @IsNotEmpty()
  circleId: string;
}
