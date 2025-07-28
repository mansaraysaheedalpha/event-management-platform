import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class AnswerQuestionDto {
  @IsUUID('4')
  @IsNotEmpty()
  questionId: string;

  @IsString()
  @IsNotEmpty()
  @Matches(/\S/, {
    message: 'answerText must contain non-whitespace characters',
  })
  @MaxLength(2000)
  answerText: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
