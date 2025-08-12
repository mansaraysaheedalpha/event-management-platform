//src/gamification/teams/dto/create-teams.dto.ts
import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class CreateTeamDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(100)
  name: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
