import { IsUUID } from 'class-validator';

// Based on the 'upvoteQuestionPayload' schema in our spec
export class UpvoteQuestionDto {
  @IsUUID(4)
  questionId: string;

  @IsUUID(4)
  idempotencyKey: string;
}
