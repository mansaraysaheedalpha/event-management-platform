//src/organizations/dto/create-new-organization.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class CreateNewOrganizationDTO {
  @IsString()
  @IsNotEmpty()
  organization_name: string;
}
