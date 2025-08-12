//src/comm/qna/dto/tag-question.dto.ts
import { IsArray, IsNotEmpty, IsString, IsUUID } from 'class-validator';

export class TagQuestionDto {
  @IsUUID('4')
  @IsNotEmpty()
  questionId: string;

  @IsArray()
  @IsString({ each: true })
  tags: string[];

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
