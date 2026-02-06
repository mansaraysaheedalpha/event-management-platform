// src/magic-link/dto/validate-magic-link.dto.ts
import { IsString, IsNotEmpty } from 'class-validator';

export class ValidateMagicLinkDto {
  @IsString()
  @IsNotEmpty()
  token: string;
}
