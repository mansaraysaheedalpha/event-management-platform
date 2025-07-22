import { IsString } from 'class-validator';

export class TwoFactorDTO {
  @IsString()
  code: string;
}
