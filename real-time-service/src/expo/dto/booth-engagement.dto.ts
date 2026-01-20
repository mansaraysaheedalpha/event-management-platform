// src/expo/dto/booth-engagement.dto.ts
import { IsOptional, IsObject, IsUUID } from 'class-validator';

export class TrackResourceDownloadDto {
  @IsUUID()
  boothId: string;

  @IsUUID()
  resourceId: string;
}

export class TrackCtaClickDto {
  @IsUUID()
  boothId: string;

  @IsUUID()
  ctaId: string;
}

export class CaptureLeadDto {
  @IsUUID()
  boothId: string;

  @IsOptional()
  @IsObject()
  formData?: Record<string, unknown>;
}
