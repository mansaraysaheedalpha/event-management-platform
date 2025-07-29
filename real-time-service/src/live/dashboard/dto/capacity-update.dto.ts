export class CapacityUpdateDto {
  eventId: string;
  resourceType: 'event' | 'session' | 'venue';
  resourceId: string;
  currentLevel: number;
  capacity: number;
}
