import { IsString } from 'class-validator';

export class SwitchOrganizationDTO {
  @IsString()
  organizationId: string;
}
