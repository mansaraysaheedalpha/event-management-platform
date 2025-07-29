import {
  IsEnum,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUrl,
  MaxLength,
} from 'class-validator';

enum ContentType {
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
}
