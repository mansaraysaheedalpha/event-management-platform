import { IsBoolean, IsInt, IsArray, IsString, Min } from 'class-validator';

export class PresentationStateDto {
  @IsInt()
  @Min(0)
  currentSlide: number;

  @IsInt()
  @Min(0)
  totalSlides: number;

  @IsBoolean()
  isActive: boolean;

  @IsArray()
  @IsString({ each: true })
  slideUrls: string[];
}
