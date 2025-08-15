import { IsString } from 'class-validator';

//src/auth/dto/switch-org.dto.ts
export class SwitchOrganizationDTO {
  @IsString()
  organizationId: string;
}
