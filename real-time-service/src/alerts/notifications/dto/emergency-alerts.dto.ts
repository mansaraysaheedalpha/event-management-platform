//src/alerts/notifications/dto/emergency-alerts.dto.ts
export class EmergencyAlertDto {
  type: 'EMERGENCY_ALERT';
  eventId: string; // Broadcast to the whole event
  alertType: 'MEDICAL' | 'FIRE' | 'SECURITY' | 'EVACUATION';
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}
