import { IsOptional, IsString } from 'class-validator';

export class UpdateOrganizationDTO {
  @IsOptional()
  @IsString()
  name?: string;
}
