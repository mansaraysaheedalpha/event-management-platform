// src/organizations/dto/update-member-role.dto.ts

import { IsString, IsNotEmpty } from 'class-validator';

export class UpdateMemberRoleDTO {
  @IsString()
  @IsNotEmpty()
  roleId: string;
}
