class IncidentReporterDto {
  id: string;
  firstName: string | null;
  lastName: string | null;
}

export class IncidentDto {
  id: string;
  createdAt: Date;
  updatedAt: Date;
  type: string;
  severity: string;
  status: string;
  details: string;
  reporterId: string;
  organizationId: string;
  eventId: string;
  sessionId: string;
  assigneeId: string | null;
  resolutionNotes: string | null;
  reporter: IncidentReporterDto;
}
