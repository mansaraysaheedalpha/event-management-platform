//src/live/dashboard/dto/capacity-update.dto.ts
export class CapacityUpdateDto {
  eventId: string;
  resourceType: 'event' | 'session' | 'venue';
  resourceId: string;
  currentLevel: number;
  capacity: number;
}
