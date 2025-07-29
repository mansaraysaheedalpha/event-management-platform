import { IsArray, IsNotEmpty, IsString, IsUUID } from 'class-validator';

export class TagQuestionDto {
  @IsUUID('4')
  @IsNotEmpty()
  questionId: string;

  @IsArray()
  @IsString({ each: true })
  tags: string[];
}
