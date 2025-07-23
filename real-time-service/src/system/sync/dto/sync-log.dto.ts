import { Prisma } from '@prisma/client';

export class SyncLogDto {
  id: string;
  timestamp: Date;
  resource: string;
  action: string;
  payload: Prisma.JsonValue;
}
