//src/alerts/notifications/dto/schedule-change.dto.ts
export class PersonalNotificationDto {
  type: 'PERSONAL_NOTIFICATION';
  targetUserId: string;
  title: string;
  message: string;
  actionUrl?: string;
}
