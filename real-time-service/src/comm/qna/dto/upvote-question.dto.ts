//src/comm/qna/dto/upvote-question.dto.ts
import { IsNotEmpty, IsUUID } from 'class-validator';

/**
 * DTO for upvoting a question.
 * Used when a user wants to upvote a previously asked question.
 */
export class UpvoteQuestionDto {
  @IsNotEmpty()
  @IsUUID('4')
  questionId: string;

  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
