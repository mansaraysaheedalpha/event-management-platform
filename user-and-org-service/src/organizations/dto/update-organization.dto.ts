//src/organizations/dto/update-organization.dto.ts
import { IsOptional, IsString } from 'class-validator';

export class UpdateOrganizationDTO {
  @IsOptional()
  @IsString()
  name?: string;
}
