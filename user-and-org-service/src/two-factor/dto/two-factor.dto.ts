//src/two-factor/dto/two-factor.dto.ts
import { IsString } from 'class-validator';

export class TwoFactorDTO {
  @IsString()
  code: string;
}
