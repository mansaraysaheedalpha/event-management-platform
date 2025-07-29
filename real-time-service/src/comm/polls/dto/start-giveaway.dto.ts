import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class StartGiveawayDto {
  @IsUUID('4')
  @IsNotEmpty()
  pollId: string;

  @IsUUID('4')
  @IsNotEmpty()
  winningOptionId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  prize: string;
}
