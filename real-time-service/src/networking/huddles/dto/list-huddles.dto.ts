//src/networking/huddles/dto/list-huddles.dto.ts
import { IsNotEmpty, IsOptional, IsString } from 'class-validator';

export class ListHuddlesDto {
  @IsString()
  @IsNotEmpty()
  eventId: string;
}

export class MyHuddlesDto {
  @IsString()
  @IsOptional()
  eventId?: string;
}
