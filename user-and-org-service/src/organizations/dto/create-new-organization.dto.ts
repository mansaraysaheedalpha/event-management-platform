import { IsNotEmpty, IsString } from 'class-validator';

export class CreateNewOrganizationDTO {
  @IsString()
  @IsNotEmpty()
  organization_name: string;
}
