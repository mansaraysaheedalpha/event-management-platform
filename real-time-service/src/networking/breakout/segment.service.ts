// src/networking/breakout/segment.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { AssignmentStatus } from '@prisma/client';

// Single condition for matching
interface MatchCondition {
  field: string;
  operator:
    | 'equals'
    | 'notEquals'
    | 'contains'
    | 'notContains'
    | 'startsWith'
    | 'endsWith'
    | 'in'
    | 'notIn'
    | 'gt'
    | 'gte'
    | 'lt'
    | 'lte'
    | 'exists'
    | 'regex';
  value: string | string[] | number | boolean;
}

// Compound criteria with AND/OR logic
interface MatchCriteria {
  // For backward compatibility: single condition
  field?: string;
  operator?:
    | 'equals'
    | 'notEquals'
    | 'contains'
    | 'notContains'
    | 'startsWith'
    | 'endsWith'
    | 'in'
    | 'notIn'
    | 'gt'
    | 'gte'
    | 'lt'
    | 'lte'
    | 'exists'
    | 'regex';
  value?: string | string[] | number | boolean;
  // Compound conditions
  all?: MatchCondition[]; // AND - all conditions must match
  any?: MatchCondition[]; // OR - at least one condition must match
}

interface CreateSegmentDto {
  sessionId: string;
  eventId: string;
  name: string;
  description?: string;
  color?: string;
  matchCriteria?: MatchCriteria;
  priority?: number;
}

interface CreateSegmentRuleDto {
  segmentId: string;
  roomId: string;
  maxFromSegment?: number;
}

interface AttendeeData {
  userId: string;
  registrationData?: Record<string, unknown>;
}

@Injectable()
export class SegmentService {
  private readonly logger = new Logger(SegmentService.name);

  constructor(private readonly prisma: PrismaService) {}

  // ==================
  // Segment Management
  // ==================

  async createSegment(creatorId: string, data: CreateSegmentDto) {
    return this.prisma.breakoutSegment.create({
      data: {
        sessionId: data.sessionId,
        eventId: data.eventId,
        name: data.name,
        description: data.description,
        color: data.color,
        matchCriteria: data.matchCriteria as object,
        priority: data.priority ?? 0,
        creatorId,
      },
      include: {
        creator: {
          select: { id: true, firstName: true, lastName: true },
        },
        _count: {
          select: { members: true, assignmentRules: true },
        },
      },
    });
  }

  async updateSegment(
    segmentId: string,
    data: Partial<CreateSegmentDto>,
  ) {
    return this.prisma.breakoutSegment.update({
      where: { id: segmentId },
      data: {
        name: data.name,
        description: data.description,
        color: data.color,
        matchCriteria: data.matchCriteria as object,
        priority: data.priority,
      },
      include: {
        _count: {
          select: { members: true, assignmentRules: true },
        },
      },
    });
  }

  async deleteSegment(segmentId: string) {
    return this.prisma.breakoutSegment.delete({
      where: { id: segmentId },
    });
  }

  async getSegmentsBySession(sessionId: string) {
    return this.prisma.breakoutSegment.findMany({
      where: { sessionId },
      orderBy: { priority: 'asc' },
      include: {
        creator: {
          select: { id: true, firstName: true, lastName: true },
        },
        _count: {
          select: { members: true, assignmentRules: true },
        },
        assignmentRules: {
          include: {
            room: {
              select: { id: true, name: true },
            },
          },
        },
      },
    });
  }

  // =====================
  // Segment Membership
  // =====================

  async addMemberToSegment(
    segmentId: string,
    userId: string,
    isAutoAssigned = false,
  ) {
    return this.prisma.breakoutSegmentMember.upsert({
      where: {
        segmentId_userId: { segmentId, userId },
      },
      create: {
        segmentId,
        userId,
        isAutoAssigned,
      },
      update: {
        isAutoAssigned,
      },
    });
  }

  async removeMemberFromSegment(segmentId: string, userId: string) {
    return this.prisma.breakoutSegmentMember.delete({
      where: {
        segmentId_userId: { segmentId, userId },
      },
    }).catch(() => null);
  }

  async getSegmentMembers(segmentId: string) {
    return this.prisma.breakoutSegmentMember.findMany({
      where: { segmentId },
      include: {
        user: {
          select: { id: true, firstName: true, lastName: true, email: true },
        },
      },
    });
  }

  // =====================
  // Assignment Rules
  // =====================

  async createAssignmentRule(data: CreateSegmentRuleDto) {
    return this.prisma.breakoutSegmentRule.create({
      data: {
        segmentId: data.segmentId,
        roomId: data.roomId,
        maxFromSegment: data.maxFromSegment,
      },
      include: {
        segment: {
          select: { id: true, name: true },
        },
        room: {
          select: { id: true, name: true },
        },
      },
    });
  }

  async deleteAssignmentRule(segmentId: string, roomId: string) {
    return this.prisma.breakoutSegmentRule.delete({
      where: {
        segmentId_roomId: { segmentId, roomId },
      },
    }).catch(() => null);
  }

  async getRulesForSession(sessionId: string) {
    const segments = await this.prisma.breakoutSegment.findMany({
      where: { sessionId },
      include: {
        assignmentRules: {
          include: {
            room: {
              select: { id: true, name: true, maxParticipants: true },
            },
          },
        },
      },
    });

    return segments.flatMap((s) => s.assignmentRules);
  }

  // ==============================
  // Auto-Segmentation Engine
  // ==============================

  /**
   * Get a nested field value using dot notation (e.g., "company.name", "address.city")
   */
  private getNestedValue(
    obj: Record<string, unknown>,
    path: string,
  ): unknown {
    return path.split('.').reduce((current: unknown, key: string) => {
      if (current === null || current === undefined) return undefined;
      if (typeof current !== 'object') return undefined;
      return (current as Record<string, unknown>)[key];
    }, obj);
  }

  /**
   * Match a single condition against registration data
   */
  private matchesCondition(
    condition: MatchCondition,
    registrationData: Record<string, unknown>,
  ): boolean {
    const fieldValue = this.getNestedValue(registrationData, condition.field);

    // Handle 'exists' operator separately
    if (condition.operator === 'exists') {
      const exists = fieldValue !== undefined && fieldValue !== null;
      return condition.value === true ? exists : !exists;
    }

    // For all other operators, null/undefined means no match (except notEquals/notIn/notContains)
    if (fieldValue === undefined || fieldValue === null) {
      return ['notEquals', 'notIn', 'notContains'].includes(condition.operator);
    }

    const { operator, value } = condition;

    // Numeric comparisons
    if (['gt', 'gte', 'lt', 'lte'].includes(operator)) {
      const numFieldValue = Number(fieldValue);
      const numCriteriaValue = Number(value);

      if (isNaN(numFieldValue) || isNaN(numCriteriaValue)) {
        return false;
      }

      switch (operator) {
        case 'gt':
          return numFieldValue > numCriteriaValue;
        case 'gte':
          return numFieldValue >= numCriteriaValue;
        case 'lt':
          return numFieldValue < numCriteriaValue;
        case 'lte':
          return numFieldValue <= numCriteriaValue;
        default:
          return false;
      }
    }

    // String comparisons (case-insensitive)
    const stringValue = String(fieldValue).toLowerCase();
    const criteriaValue = Array.isArray(value)
      ? value.map((v) => String(v).toLowerCase())
      : String(value).toLowerCase();

    switch (operator) {
      case 'equals':
        return stringValue === criteriaValue;

      case 'notEquals':
        return stringValue !== criteriaValue;

      case 'contains':
        return stringValue.includes(criteriaValue as string);

      case 'notContains':
        return !stringValue.includes(criteriaValue as string);

      case 'startsWith':
        return stringValue.startsWith(criteriaValue as string);

      case 'endsWith':
        return stringValue.endsWith(criteriaValue as string);

      case 'in':
        return Array.isArray(criteriaValue) && criteriaValue.includes(stringValue);

      case 'notIn':
        return Array.isArray(criteriaValue) && !criteriaValue.includes(stringValue);

      case 'regex':
        try {
          const regex = new RegExp(String(value), 'i');
          return regex.test(String(fieldValue));
        } catch {
          this.logger.warn(`Invalid regex pattern: ${value}`);
          return false;
        }

      default:
        return false;
    }
  }

  /**
   * Match an attendee's registration data against segment criteria
   * Supports:
   * - Single condition (backward compatible)
   * - Compound conditions with 'all' (AND) and 'any' (OR)
   * - Nested field access via dot notation (e.g., "company.name")
   * - Operators: equals, notEquals, contains, notContains, startsWith, endsWith,
   *              in, notIn, gt, gte, lt, lte, exists, regex
   */
  matchesCriteria(
    criteria: MatchCriteria,
    registrationData: Record<string, unknown>,
  ): boolean {
    // Handle compound 'all' conditions (AND)
    if (criteria.all && criteria.all.length > 0) {
      const allMatch = criteria.all.every((condition) =>
        this.matchesCondition(condition, registrationData),
      );
      // If there's also an 'any' condition, both must be satisfied
      if (criteria.any && criteria.any.length > 0) {
        const anyMatch = criteria.any.some((condition) =>
          this.matchesCondition(condition, registrationData),
        );
        return allMatch && anyMatch;
      }
      return allMatch;
    }

    // Handle compound 'any' conditions (OR)
    if (criteria.any && criteria.any.length > 0) {
      return criteria.any.some((condition) =>
        this.matchesCondition(condition, registrationData),
      );
    }

    // Handle single condition (backward compatible)
    if (criteria.field && criteria.operator) {
      return this.matchesCondition(
        {
          field: criteria.field,
          operator: criteria.operator,
          value: criteria.value ?? '',
        },
        registrationData,
      );
    }

    // No valid criteria
    return false;
  }

  /**
   * Auto-assign attendees to segments based on their registration data
   */
  async autoAssignToSegments(
    sessionId: string,
    attendees: AttendeeData[],
  ): Promise<{ segmentId: string; userId: string }[]> {
    const segments = await this.prisma.breakoutSegment.findMany({
      where: { sessionId },
      orderBy: { priority: 'asc' },
    });

    const assignments: { segmentId: string; userId: string }[] = [];

    for (const attendee of attendees) {
      if (!attendee.registrationData) continue;

      for (const segment of segments) {
        if (!segment.matchCriteria) continue;

        const criteria = segment.matchCriteria as unknown as MatchCriteria;
        if (this.matchesCriteria(criteria, attendee.registrationData)) {
          await this.addMemberToSegment(segment.id, attendee.userId, true);
          assignments.push({ segmentId: segment.id, userId: attendee.userId });
          break; // Only assign to first matching segment (based on priority)
        }
      }
    }

    return assignments;
  }

  // ================================
  // Room Assignment Computation
  // ================================

  /**
   * Compute and store room assignments for a session based on segment rules
   */
  async computeRoomAssignments(sessionId: string, eventId: string): Promise<{
    created: number;
    errors: string[];
  }> {
    const errors: string[] = [];
    let created = 0;

    // Get all segments with their rules and members
    const segments = await this.prisma.breakoutSegment.findMany({
      where: { sessionId },
      orderBy: { priority: 'asc' },
      include: {
        members: true,
        assignmentRules: {
          include: {
            room: {
              include: {
                _count: { select: { assignments: true } },
              },
            },
          },
        },
      },
    });

    // Track room capacities
    const roomCapacities = new Map<string, { max: number; current: number }>();

    // Process each segment
    for (const segment of segments) {
      for (const member of segment.members) {
        // Check if user already has an assignment for this session
        const existingAssignment = await this.prisma.breakoutRoomAssignment.findUnique({
          where: {
            sessionId_userId: { sessionId, userId: member.userId },
          },
        });

        if (existingAssignment) continue;

        // Find a suitable room from the rules
        for (const rule of segment.assignmentRules) {
          const roomId = rule.roomId;
          const room = rule.room;

          // Initialize room capacity tracking
          if (!roomCapacities.has(roomId)) {
            const currentAssignments = await this.prisma.breakoutRoomAssignment.count({
              where: { roomId },
            });
            roomCapacities.set(roomId, {
              max: room.maxParticipants,
              current: currentAssignments,
            });
          }

          const capacity = roomCapacities.get(roomId)!;

          // Check room capacity
          if (capacity.current >= capacity.max) continue;

          // Check segment limit for this room
          if (rule.maxFromSegment) {
            const segmentCount = await this.prisma.breakoutRoomAssignment.count({
              where: { roomId, segmentId: segment.id },
            });
            if (segmentCount >= rule.maxFromSegment) continue;
          }

          // Create the assignment
          try {
            await this.prisma.breakoutRoomAssignment.create({
              data: {
                sessionId,
                eventId,
                userId: member.userId,
                roomId,
                segmentId: segment.id,
                status: AssignmentStatus.PENDING,
              },
            });
            capacity.current++;
            created++;
          } catch (error) {
            errors.push(`Failed to assign user ${member.userId}: ${error}`);
          }
          break; // Move to next member after successful assignment
        }
      }
    }

    this.logger.log(`Created ${created} room assignments for session ${sessionId}`);
    return { created, errors };
  }

  // ================================
  // Assignment Queries
  // ================================

  async getUserAssignment(sessionId: string, userId: string) {
    return this.prisma.breakoutRoomAssignment.findUnique({
      where: {
        sessionId_userId: { sessionId, userId },
      },
      include: {
        room: {
          select: {
            id: true,
            name: true,
            topic: true,
            status: true,
            durationMinutes: true,
            facilitator: {
              select: { id: true, firstName: true, lastName: true },
            },
            _count: { select: { participants: true } },
          },
        },
      },
    });
  }

  async getSessionAssignments(sessionId: string) {
    return this.prisma.breakoutRoomAssignment.findMany({
      where: { sessionId },
      include: {
        user: {
          select: { id: true, firstName: true, lastName: true, email: true },
        },
        room: {
          select: { id: true, name: true },
        },
      },
    });
  }

  async updateAssignmentStatus(
    sessionId: string,
    userId: string,
    status: AssignmentStatus,
  ) {
    return this.prisma.breakoutRoomAssignment.update({
      where: {
        sessionId_userId: { sessionId, userId },
      },
      data: {
        status,
        notifiedAt: status === AssignmentStatus.NOTIFIED ? new Date() : undefined,
      },
    });
  }

  async notifyAllAssignments(sessionId: string) {
    return this.prisma.breakoutRoomAssignment.updateMany({
      where: {
        sessionId,
        status: AssignmentStatus.PENDING,
      },
      data: {
        status: AssignmentStatus.NOTIFIED,
        notifiedAt: new Date(),
      },
    });
  }

  async clearSessionAssignments(sessionId: string) {
    return this.prisma.breakoutRoomAssignment.deleteMany({
      where: { sessionId },
    });
  }
}
