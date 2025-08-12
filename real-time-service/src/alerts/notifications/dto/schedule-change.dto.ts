//src/alerts/notifications/dto/schedule-change.dto.ts
export class ScheduleChangeDto {
  type: 'SCHEDULE_CHANGE';
  eventId: string; // Broadcast to the whole event
  changeType: 'TIME_CHANGE' | 'ROOM_CHANGE' | 'CANCELLATION';
  details: string; // e.g., "Session 'Keynote' has been moved to Hall B"
}
