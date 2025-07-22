import { IsUUID } from 'class-validator';

export class SubmitVoteDto {
  @IsUUID(4)
  pollId: string;

  @IsUUID(4)
  optionId: string;

  @IsUUID(4)
  idempotencyKey: string;
}
