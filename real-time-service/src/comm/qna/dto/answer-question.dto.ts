import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class AnswerQuestionDto {
  @IsUUID('4')
  @IsNotEmpty()
  questionId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(2000)
  answerText: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
