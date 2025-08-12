//src/networking/proximity/dto/proximity-location.dto.ts
import { IsLatitude, IsLongitude, IsNotEmpty, IsUUID } from 'class-validator';

export class UpdateLocationDto {
  @IsLatitude()
  latitude: number;

  @IsLongitude()
  longitude: number;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
