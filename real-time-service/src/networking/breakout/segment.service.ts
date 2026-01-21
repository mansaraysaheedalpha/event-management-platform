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

// Valid operators for match criteria
const VALID_OPERATORS = [
  'equals', 'notEquals', 'contains', 'notContains',
  'startsWith', 'endsWith', 'in', 'notIn',
  'gt', 'gte', 'lt', 'lte', 'exists', 'regex',
] as const;

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

  /**
   * Validate a single match condition
   */
  private validateCondition(condition: MatchCondition): { valid: boolean; error?: string } {
    if (!condition.field || typeof condition.field !== 'string') {
      return { valid: false, error: 'Condition must have a valid field name' };
    }

    if (condition.field.length > 100) {
      return { valid: false, error: 'Field name too long (max 100 characters)' };
    }

    if (!VALID_OPERATORS.includes(condition.operator as typeof VALID_OPERATORS[number])) {
      return { valid: false, error: `Invalid operator: ${condition.operator}` };
    }

    // Validate value based on operator
    if (condition.operator === 'in' || condition.operator === 'notIn') {
      if (!Array.isArray(condition.value)) {
        return { valid: false, error: `Operator ${condition.operator} requires an array value` };
      }
      if (condition.value.length > 100) {
        return { valid: false, error: 'Array value too long (max 100 items)' };
      }
    }

    if (condition.operator === 'exists') {
      if (typeof condition.value !== 'boolean') {
        return { valid: false, error: 'Operator exists requires a boolean value' };
      }
    }

    if (condition.operator === 'regex') {
      try {
        new RegExp(String(condition.value));
      } catch {
        return { valid: false, error: 'Invalid regex pattern' };
      }
    }

    return { valid: true };
  }

  /**
   * Validate match criteria JSON structure
   */
  private validateMatchCriteria(criteria: unknown): { valid: boolean; error?: string } {
    if (!criteria || typeof criteria !== 'object') {
      return { valid: false, error: 'Match criteria must be an object' };
    }

    const c = criteria as MatchCriteria;

    // Check for compound conditions
    if (c.all) {
      if (!Array.isArray(c.all)) {
        return { valid: false, error: '"all" must be an array' };
      }
      if (c.all.length > 10) {
        return { valid: false, error: 'Too many conditions in "all" (max 10)' };
      }
      for (const condition of c.all) {
        const result = this.validateCondition(condition);
        if (!result.valid) return result;
      }
    }

    if (c.any) {
      if (!Array.isArray(c.any)) {
        return { valid: false, error: '"any" must be an array' };
      }
      if (c.any.length > 10) {
        return { valid: false, error: 'Too many conditions in "any" (max 10)' };
      }
      for (const condition of c.any) {
        const result = this.validateCondition(condition);
        if (!result.valid) return result;
      }
    }

    // Check for single condition (backward compatible)
    if (c.field && c.operator) {
      const result = this.validateCondition({
        field: c.field,
        operator: c.operator,
        value: c.value ?? '',
      });
      if (!result.valid) return result;
    }

    // Must have at least one valid criteria
    const hasConditions = (c.all && c.all.length > 0) ||
                          (c.any && c.any.length > 0) ||
                          (c.field && c.operator);

    if (!hasConditions) {
      return { valid: false, error: 'Match criteria must have at least one condition' };
    }

    return { valid: true };
  }

  // ==================
  // Segment Management
  // ==================

  async createSegment(creatorId: string, data: CreateSegmentDto) {
    // Validate matchCriteria if provided
    if (data.matchCriteria) {
      const validation = this.validateMatchCriteria(data.matchCriteria);
      if (!validation.valid) {
        throw new Error(`Invalid match criteria: ${validation.error}`);
      }
    }

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
    // Validate matchCriteria if provided
    if (data.matchCriteria) {
      const validation = this.validateMatchCriteria(data.matchCriteria);
      if (!validation.valid) {
        throw new Error(`Invalid match criteria: ${validation.error}`);
      }
    }

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
   * Compute and store room assignments for a session based on segment rules.
   * This function first auto-assigns users to segments based on match criteria,
   * then assigns segment members to breakout rooms.
   *
   * OPTIMIZED: Uses batch queries instead of N+1 queries for better performance.
   */
  async computeRoomAssignments(sessionId: string, eventId: string): Promise<{
    created: number;
    errors: string[];
  }> {
    const errors: string[] = [];
    let created = 0;

    // Use a transaction to ensure data consistency
    return this.prisma.$transaction(async (tx) => {
      // Step 1: Get all segments with their match criteria
      const segmentsForMatching = await tx.breakoutSegment.findMany({
        where: { sessionId },
        orderBy: { priority: 'asc' },
      });

      // Step 2: Auto-assign users to segments based on profile data
      // Get all user profiles that could be matched
      const userProfiles = await tx.userProfile.findMany({
        select: {
          userId: true,
          currentRole: true,
          industry: true,
          company: true,
          interests: true,
          goals: true,
          experienceLevel: true,
          linkedInUrl: true,
          bio: true,
        },
      });

      this.logger.log(`Found ${userProfiles.length} user profiles to match against ${segmentsForMatching.length} segments`);

      // BATCH: Get all existing segment memberships at once
      const existingMemberships = await tx.breakoutSegmentMember.findMany({
        where: {
          segmentId: { in: segmentsForMatching.map((s) => s.id) },
        },
        select: { segmentId: true, userId: true },
      });

      // Create a Set for O(1) lookup
      const membershipSet = new Set(
        existingMemberships.map((m) => `${m.segmentId}:${m.userId}`),
      );

      // Batch create new segment memberships
      const newMemberships: { segmentId: string; userId: string; isAutoAssigned: boolean }[] = [];

      for (const profile of userProfiles) {
        const profileData: Record<string, unknown> = {
          jobRole: profile.currentRole,
          industry: profile.industry,
          company: profile.company,
          interests: profile.interests,
          goals: profile.goals,
          experienceLevel: profile.experienceLevel,
          linkedInUrl: profile.linkedInUrl,
          bio: profile.bio,
        };

        for (const segment of segmentsForMatching) {
          if (!segment.matchCriteria) continue;

          const key = `${segment.id}:${profile.userId}`;
          if (membershipSet.has(key)) continue;

          const criteria = segment.matchCriteria as unknown as MatchCriteria;
          if (this.matchesCriteria(criteria, profileData)) {
            newMemberships.push({
              segmentId: segment.id,
              userId: profile.userId,
              isAutoAssigned: true,
            });
            membershipSet.add(key); // Track to prevent duplicates in batch
            break; // Only assign to first matching segment
          }
        }
      }

      // Batch insert all new memberships
      if (newMemberships.length > 0) {
        await tx.breakoutSegmentMember.createMany({
          data: newMemberships,
          skipDuplicates: true,
        });
        this.logger.log(`Auto-assigned ${newMemberships.length} users to segments`);
      }

      // Step 3: Get all segments with their rules and updated members
      const segments = await tx.breakoutSegment.findMany({
        where: { sessionId },
        orderBy: { priority: 'asc' },
        include: {
          members: true,
          assignmentRules: {
            include: {
              room: {
                select: { id: true, maxParticipants: true },
              },
            },
          },
        },
      });

      // BATCH: Get all existing room assignments for this session
      const existingAssignments = await tx.breakoutRoomAssignment.findMany({
        where: { sessionId },
        select: { userId: true, roomId: true, segmentId: true },
      });

      // Create Sets for O(1) lookup
      const assignedUserIds = new Set(existingAssignments.map((a) => a.userId));

      // BATCH: Get all room assignment counts at once
      const roomIds = segments.flatMap((s) => s.assignmentRules.map((r) => r.roomId));
      const uniqueRoomIds = [...new Set(roomIds)];

      const roomAssignmentCounts = await tx.breakoutRoomAssignment.groupBy({
        by: ['roomId'],
        where: { roomId: { in: uniqueRoomIds } },
        _count: { roomId: true },
      });

      // BATCH: Get segment assignment counts per room
      const segmentRoomCounts = await tx.breakoutRoomAssignment.groupBy({
        by: ['roomId', 'segmentId'],
        where: {
          roomId: { in: uniqueRoomIds },
          segmentId: { not: null },
        },
        _count: { roomId: true },
      });

      // Build lookup maps
      const roomCapacities = new Map<string, { max: number; current: number }>();
      for (const segment of segments) {
        for (const rule of segment.assignmentRules) {
          if (!roomCapacities.has(rule.roomId)) {
            const countEntry = roomAssignmentCounts.find((c) => c.roomId === rule.roomId);
            roomCapacities.set(rule.roomId, {
              max: rule.room.maxParticipants,
              current: countEntry?._count.roomId ?? 0,
            });
          }
        }
      }

      const segmentRoomCountMap = new Map<string, number>();
      for (const entry of segmentRoomCounts) {
        const key = `${entry.segmentId}:${entry.roomId}`;
        segmentRoomCountMap.set(key, entry._count.roomId);
      }

      // Batch create new assignments
      const newAssignments: {
        sessionId: string;
        eventId: string;
        userId: string;
        roomId: string;
        segmentId: string;
        status: AssignmentStatus;
      }[] = [];

      // Process each segment
      for (const segment of segments) {
        for (const member of segment.members) {
          // Skip if user already has an assignment
          if (assignedUserIds.has(member.userId)) continue;

          // Find a suitable room from the rules
          for (const rule of segment.assignmentRules) {
            const roomId = rule.roomId;
            const capacity = roomCapacities.get(roomId)!;

            // Check room capacity
            if (capacity.current >= capacity.max) continue;

            // Check segment limit for this room
            if (rule.maxFromSegment) {
              const segmentKey = `${segment.id}:${roomId}`;
              const currentSegmentCount = segmentRoomCountMap.get(segmentKey) ?? 0;
              if (currentSegmentCount >= rule.maxFromSegment) continue;
              // Update the count for subsequent iterations
              segmentRoomCountMap.set(segmentKey, currentSegmentCount + 1);
            }

            // Queue the assignment
            newAssignments.push({
              sessionId,
              eventId,
              userId: member.userId,
              roomId,
              segmentId: segment.id,
              status: AssignmentStatus.PENDING,
            });

            // Update tracking
            capacity.current++;
            assignedUserIds.add(member.userId);
            created++;
            break; // Move to next member after successful assignment
          }
        }
      }

      // Batch insert all assignments
      if (newAssignments.length > 0) {
        try {
          await tx.breakoutRoomAssignment.createMany({
            data: newAssignments,
            skipDuplicates: true,
          });
        } catch (error) {
          errors.push(`Batch assignment creation failed: ${error}`);
          created = 0; // Reset count on failure
        }
      }

      this.logger.log(`Created ${created} room assignments for session ${sessionId}`);
      return { created, errors };
    }, {
      timeout: 30000, // 30 second timeout for large operations
    });
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

  // ================================
  // User Profile for Segmentation
  // ================================

  /**
   * Update user profile for segmentation matching.
   * These fields are used to auto-assign users to segments.
   */
  async updateUserProfile(
    userId: string,
    data: {
      currentRole?: string;
      company?: string;
      industry?: string;
      experienceLevel?: string;
      interests?: string[];
    },
  ) {
    return this.prisma.userProfile.upsert({
      where: { userId },
      create: {
        userId,
        currentRole: data.currentRole,
        company: data.company,
        industry: data.industry,
        experienceLevel: data.experienceLevel,
        interests: data.interests || [],
        goals: [],
      },
      update: {
        currentRole: data.currentRole,
        company: data.company,
        industry: data.industry,
        experienceLevel: data.experienceLevel,
        interests: data.interests,
        updatedAt: new Date(),
      },
    });
  }

  /**
   * Get user profile for segmentation
   */
  async getUserProfile(userId: string) {
    return this.prisma.userProfile.findUnique({
      where: { userId },
      select: {
        userId: true,
        currentRole: true,
        company: true,
        industry: true,
        experienceLevel: true,
        interests: true,
      },
    });
  }
}
