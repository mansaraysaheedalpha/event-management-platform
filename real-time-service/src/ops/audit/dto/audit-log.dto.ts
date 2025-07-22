export class AuditLogDto {
  id: string;
  action: string;
  actingUserId: string;
  organizationId: string;
  // ... any other fields returned by your User & Org service's audit log endpoint
}
