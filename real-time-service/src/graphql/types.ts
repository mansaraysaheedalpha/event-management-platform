import { ObjectType, Field, ID, registerEnumType } from '@nestjs/graphql';
import { Directive } from '@nestjs/graphql';

export enum IncidentType {
  HARASSMENT = 'HARASSMENT',
  MEDICAL = 'MEDICAL',
  TECHNICAL = 'TECHNICAL',
  SECURITY = 'SECURITY',
  ACCESSIBILITY = 'ACCESSIBILITY',
}

export enum IncidentStatus {
  REPORTED = 'REPORTED',
  ACKNOWLEDGED = 'ACKNOWLEDGED',
  INVESTIGATING = 'INVESTIGATING',
  RESOLVED = 'RESOLVED',
}

export enum IncidentSeverity {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}

registerEnumType(IncidentType, {
  name: 'IncidentType',
});

registerEnumType(IncidentStatus, {
  name: 'IncidentStatus',
});

registerEnumType(IncidentSeverity, {
  name: 'IncidentSeverity',
});

@ObjectType()
@Directive('@key(fields: "id")')
export class UserReferenceType {
  @Field(() => ID)
  @Directive('@external')
  id: string;
}

@ObjectType()
export class IncidentTypeObject {
  @Field(() => ID)
  id: string;

  @Field()
  createdAt: Date;

  @Field()
  updatedAt: Date;

  @Field(() => IncidentType)
  type: IncidentType;

  @Field(() => IncidentSeverity)
  severity: IncidentSeverity;

  @Field(() => IncidentStatus)
  status: IncidentStatus;

  @Field()
  details: string;

  @Field(() => UserReferenceType)
  reporter: UserReferenceType;

  @Field()
  organizationId: string;

  @Field()
  eventId: string;

  @Field()
  sessionId: string;

  @Field(() => UserReferenceType, { nullable: true })
  assignee?: UserReferenceType;

  @Field({ nullable: true })
  resolutionNotes?: string;
}
