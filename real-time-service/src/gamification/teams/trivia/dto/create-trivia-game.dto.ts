// src/gamification/teams/trivia/dto/create-trivia-game.dto.ts
import {
  IsNotEmpty,
  IsString,
  IsInt,
  IsArray,
  ValidateNested,
  ArrayMinSize,
  ArrayMaxSize,
  Min,
  Max,
  MaxLength,
  IsOptional,
  Validate,
  ValidatorConstraint,
  ValidatorConstraintInterface,
  ValidationArguments,
} from 'class-validator';
import { Type } from 'class-transformer';

/**
 * Validates that correctIndex is within the bounds of the options array.
 */
@ValidatorConstraint({ name: 'correctIndexBounds', async: false })
class CorrectIndexBoundsValidator implements ValidatorConstraintInterface {
  validate(correctIndex: number, args: ValidationArguments) {
    const obj = args.object as TriviaQuestionDto;
    return (
      Number.isInteger(correctIndex) &&
      correctIndex >= 0 &&
      Array.isArray(obj.options) &&
      correctIndex < obj.options.length
    );
  }

  defaultMessage() {
    return 'correctIndex must be a valid index within the options array';
  }
}

export class TriviaQuestionDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(500)
  questionText: string;

  @IsArray()
  @IsString({ each: true })
  @ArrayMinSize(2)
  @ArrayMaxSize(10)
  @MaxLength(500, { each: true })
  options: string[];

  @IsInt()
  @Min(0)
  @Validate(CorrectIndexBoundsValidator)
  correctIndex: number;
}

export class CreateTriviaGameDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  name: string;

  @IsOptional()
  @IsInt()
  @Min(5)
  @Max(120)
  timePerQuestion?: number;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(100)
  pointsCorrect?: number;

  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(100)
  pointsSpeedBonus?: number;

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => TriviaQuestionDto)
  @ArrayMinSize(1)
  @ArrayMaxSize(100)
  questions: TriviaQuestionDto[];

  @IsString()
  @IsNotEmpty()
  idempotencyKey: string;
}
