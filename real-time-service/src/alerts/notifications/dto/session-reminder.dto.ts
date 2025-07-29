interface SessionDetails {
  id: string;
  title: string;
  startTime: string;
}

export class SessionReminderDto {
  type: 'SESSION_REMINDER';
  targetUserId: string;
  sessionData: SessionDetails;
  minutesUntilStart: number;
}
