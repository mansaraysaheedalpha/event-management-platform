import { IsString } from 'class-validator';

//src/auth/dto/request-reset.dto.ts
export class SwitchOrganizationDTO {
  @IsString()
  organizationId: string;
}
