//src/content/dto/drop-content.dto.ts
import {
  IsEnum,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUrl,
  IsUUID,
  MaxLength,
} from 'class-validator';

export enum ContentType {
  DOCUMENT = 'DOCUMENT',
  LINK = 'LINK',
  VIDEO = 'VIDEO',
  IMAGE = 'IMAGE',
}

export class DropContentDto {
  @IsEnum(ContentType)
  contentType: ContentType;

  @IsUrl()
  contentUrl: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  title: string;

  @IsString()
  @IsOptional()
  @MaxLength(1000)
  description?: string;

  @IsUUID('4')
  idempotencyKey: string;
}
