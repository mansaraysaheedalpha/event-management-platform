//src/shared/services/session-validation.service.ts
import {
  Injectable,
  ForbiddenException,
  NotFoundException,
  Logger,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { EventRegistrationValidationService } from './event-registration-validation.service';

/**
 * SessionValidationService provides centralized session membership validation.
 * Ensures users can only access sessions they are participants of AND
 * are registered for the event the session belongs to.
 */
@Injectable()
export class SessionValidationService {
  private readonly logger = new Logger(SessionValidationService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly eventRegistrationValidationService: EventRegistrationValidationService,
  ) {}

  /**
   * Validates that a user is a participant in a session AND
   * is registered for the event the session belongs to.
   * @param userId - The ID of the user to validate.
   * @param sessionId - The ID of the session to check.
   * @param skipEventRegistrationCheck - If true, only check session membership (for admins).
   * @returns The session object with participants and eventId if valid.
   * @throws NotFoundException if session doesn't exist.
   * @throws ForbiddenException if user is not a participant or not registered.
   */
  async validateSessionMembership(
    userId: string,
    sessionId: string,
    skipEventRegistrationCheck = false,
  ): Promise<{ participants: string[]; eventId: string }> {
    const session = await this.prisma.chatSession.findUnique({
      where: { id: sessionId },
      select: { participants: true, eventId: true },
    });

    if (!session) {
      this.logger.warn(`Session ${sessionId} not found`);
      throw new NotFoundException('Session not found.');
    }

    const participants = session.participants as string[];
    if (!participants.includes(userId)) {
      this.logger.warn(
        `User ${userId} attempted to access session ${sessionId} without membership`,
      );
      throw new ForbiddenException(
        'You are not a participant in this session.',
      );
    }

    // Validate event registration (unless explicitly skipped for admins)
    if (!skipEventRegistrationCheck) {
      await this.eventRegistrationValidationService.validateEventRegistration(
        userId,
        session.eventId,
      );
    }

    return { participants, eventId: session.eventId };
  }

  /**
   * Checks if a user is a participant in a session without throwing.
   * Also checks event registration by default.
   * @param userId - The ID of the user to check.
   * @param sessionId - The ID of the session to check.
   * @param skipEventRegistrationCheck - If true, only check session membership.
   * @returns True if user is a participant (and registered for event), false otherwise.
   */
  async isSessionParticipant(
    userId: string,
    sessionId: string,
    skipEventRegistrationCheck = false,
  ): Promise<boolean> {
    const session = await this.prisma.chatSession.findUnique({
      where: { id: sessionId },
      select: { participants: true, eventId: true },
    });

    if (!session) {
      return false;
    }

    const participants = session.participants as string[];
    if (!participants.includes(userId)) {
      return false;
    }

    // Check event registration if not skipped
    if (!skipEventRegistrationCheck) {
      const isRegistered =
        await this.eventRegistrationValidationService.isUserRegistered(
          userId,
          session.eventId,
        );
      return isRegistered;
    }

    return true;
  }
}
