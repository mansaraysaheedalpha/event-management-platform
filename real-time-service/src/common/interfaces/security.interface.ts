export interface SecurityAlertPayload {
  type: 'BRUTE_FORCE_SUSPECTED' | 'UNUSUAL_LOGIN' | 'PERMISSION_CHANGE';
  actingUserId: string;
  organizationId: string;
  details?: Record<string, any>;
}
