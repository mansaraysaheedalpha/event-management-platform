//src/comm/polls/dto/submit-vote.dto.ts
import { IsNotEmpty, IsUUID } from 'class-validator';

/**
 * DTO for submitting a vote on a poll option.
 * Includes poll ID, option ID, and idempotency key.
 */
export class SubmitVoteDto {
  @IsNotEmpty()
  @IsUUID('4')
  pollId: string;

  @IsNotEmpty()
  @IsUUID('4')
  optionId: string;

  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
