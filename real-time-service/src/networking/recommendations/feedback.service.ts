//src/networking/recommendations/feedback.service.ts
import {
  Injectable,
  Logger,
  NotFoundException,
  BadRequestException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { RecommendationAction } from '@prisma/client';

/**
 * Connection feedback data
 */
export interface ConnectionFeedbackData {
  connectionId: string;
  rating: number;
  wasValuable?: boolean;
  willFollowUp?: boolean;
  wouldRecommend?: boolean;
  positiveFactors?: string[];
  negativeFactors?: string[];
  comments?: string;
}

/**
 * Recommendation feedback data
 */
export interface RecommendationFeedbackData {
  recommendationId: string;
  action: RecommendationAction;
  connectionRating?: number;
  skipReason?: string;
}

/**
 * Feedback aggregation for analytics
 */
export interface FeedbackAggregation {
  averageRating: number;
  totalFeedback: number;
  positiveCount: number;
  negativeCount: number;
  topPositiveFactors: Array<{ factor: string; count: number }>;
  topNegativeFactors: Array<{ factor: string; count: number }>;
  followUpRate: number;
  recommendRate: number;
}

/**
 * FeedbackService handles collection and analysis of feedback on connections
 * and recommendations. This data is used to improve the recommendation algorithm.
 */
@Injectable()
export class FeedbackService {
  private readonly logger = new Logger(FeedbackService.name);

  constructor(private readonly prisma: PrismaService) {}

  /**
   * Submit feedback for a connection
   */
  async submitConnectionFeedback(
    userId: string,
    data: ConnectionFeedbackData,
  ): Promise<void> {
    // Verify the connection exists and user is part of it
    const connection = await this.prisma.connection.findUnique({
      where: { id: data.connectionId },
      select: { userAId: true, userBId: true },
    });

    if (!connection) {
      throw new NotFoundException('Connection not found');
    }

    if (connection.userAId !== userId && connection.userBId !== userId) {
      throw new BadRequestException(
        'You can only provide feedback for your own connections',
      );
    }

    // Validate rating
    if (data.rating < 1 || data.rating > 5) {
      throw new BadRequestException('Rating must be between 1 and 5');
    }

    // Create or update feedback
    await this.prisma.connectionFeedback.upsert({
      where: {
        connectionId_userId: {
          connectionId: data.connectionId,
          userId,
        },
      },
      create: {
        connectionId: data.connectionId,
        userId,
        rating: data.rating,
        wasValuable: data.wasValuable,
        willFollowUp: data.willFollowUp,
        wouldRecommend: data.wouldRecommend,
        positiveFactors: data.positiveFactors || [],
        negativeFactors: data.negativeFactors || [],
        comments: data.comments,
      },
      update: {
        rating: data.rating,
        wasValuable: data.wasValuable,
        willFollowUp: data.willFollowUp,
        wouldRecommend: data.wouldRecommend,
        positiveFactors: data.positiveFactors || [],
        negativeFactors: data.negativeFactors || [],
        comments: data.comments,
      },
    });

    this.logger.log(
      `Connection feedback submitted for ${data.connectionId} by user ${userId}`,
    );
  }

  /**
   * Submit feedback for a recommendation (track user action)
   */
  async submitRecommendationFeedback(
    userId: string,
    data: RecommendationFeedbackData,
  ): Promise<void> {
    // Verify the recommendation exists and belongs to the user
    const recommendation = await this.prisma.recommendation.findUnique({
      where: { id: data.recommendationId },
      select: { userId: true },
    });

    if (!recommendation) {
      throw new NotFoundException('Recommendation not found');
    }

    if (recommendation.userId !== userId) {
      throw new BadRequestException(
        'You can only provide feedback for your own recommendations',
      );
    }

    // Validate connection rating if provided
    if (
      data.connectionRating !== undefined &&
      (data.connectionRating < 1 || data.connectionRating > 5)
    ) {
      throw new BadRequestException('Connection rating must be between 1 and 5');
    }

    // Create or update feedback
    await this.prisma.recommendationFeedback.upsert({
      where: {
        recommendationId_userId: {
          recommendationId: data.recommendationId,
          userId,
        },
      },
      create: {
        recommendationId: data.recommendationId,
        userId,
        action: data.action,
        connectionRating: data.connectionRating,
        skipReason: data.skipReason,
      },
      update: {
        action: data.action,
        connectionRating: data.connectionRating,
        skipReason: data.skipReason,
      },
    });

    this.logger.log(
      `Recommendation feedback submitted: ${data.action} for ${data.recommendationId}`,
    );
  }

  /**
   * Get aggregated feedback for an event (for analytics).
   *
   * Uses DB-level aggregation where possible to reduce memory usage.
   * Factor counting still requires fetching records (Prisma limitation
   * with array fields), but we only select the needed columns.
   */
  async getEventFeedbackAggregation(
    eventId: string,
  ): Promise<FeedbackAggregation> {
    // First, get connection IDs for this event (lightweight query)
    const connections = await this.prisma.connection.findMany({
      where: { eventId },
      select: { id: true },
    });

    if (connections.length === 0) {
      return {
        averageRating: 0,
        totalFeedback: 0,
        positiveCount: 0,
        negativeCount: 0,
        topPositiveFactors: [],
        topNegativeFactors: [],
        followUpRate: 0,
        recommendRate: 0,
      };
    }

    const connectionIds = connections.map((c) => c.id);

    // Run DB-level aggregations in parallel
    const [
      totalAndAvg,
      positiveCount,
      negativeCount,
      followUpCount,
      recommendCount,
      factorData,
    ] = await Promise.all([
      // Total count and average rating
      this.prisma.connectionFeedback.aggregate({
        where: { connectionId: { in: connectionIds } },
        _count: true,
        _avg: { rating: true },
      }),
      // Positive feedback count (rating >= 4)
      this.prisma.connectionFeedback.count({
        where: { connectionId: { in: connectionIds }, rating: { gte: 4 } },
      }),
      // Negative feedback count (rating <= 2)
      this.prisma.connectionFeedback.count({
        where: { connectionId: { in: connectionIds }, rating: { lte: 2 } },
      }),
      // Will follow up count
      this.prisma.connectionFeedback.count({
        where: { connectionId: { in: connectionIds }, willFollowUp: true },
      }),
      // Would recommend count
      this.prisma.connectionFeedback.count({
        where: { connectionId: { in: connectionIds }, wouldRecommend: true },
      }),
      // Fetch only factor arrays for factor counting (minimal data transfer)
      this.prisma.connectionFeedback.findMany({
        where: { connectionId: { in: connectionIds } },
        select: { positiveFactors: true, negativeFactors: true },
      }),
    ]);

    const totalFeedback = totalAndAvg._count;
    const averageRating = totalAndAvg._avg.rating ?? 0;

    if (totalFeedback === 0) {
      return {
        averageRating: 0,
        totalFeedback: 0,
        positiveCount: 0,
        negativeCount: 0,
        topPositiveFactors: [],
        topNegativeFactors: [],
        followUpRate: 0,
        recommendRate: 0,
      };
    }

    // Count factors (must be done in-memory due to array field)
    const positiveFactorCounts = new Map<string, number>();
    const negativeFactorCounts = new Map<string, number>();

    for (const f of factorData) {
      for (const factor of f.positiveFactors) {
        positiveFactorCounts.set(
          factor,
          (positiveFactorCounts.get(factor) || 0) + 1,
        );
      }
      for (const factor of f.negativeFactors) {
        negativeFactorCounts.set(
          factor,
          (negativeFactorCounts.get(factor) || 0) + 1,
        );
      }
    }

    // Sort factors by count and take top 5
    const topPositiveFactors = Array.from(positiveFactorCounts.entries())
      .map(([factor, count]) => ({ factor, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    const topNegativeFactors = Array.from(negativeFactorCounts.entries())
      .map(([factor, count]) => ({ factor, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    return {
      averageRating,
      totalFeedback,
      positiveCount,
      negativeCount,
      topPositiveFactors,
      topNegativeFactors,
      followUpRate: (followUpCount / totalFeedback) * 100,
      recommendRate: (recommendCount / totalFeedback) * 100,
    };
  }

  /**
   * Get feedback status for a user's connections (to show prompts)
   */
  async getUserFeedbackStatus(
    userId: string,
    eventId: string,
  ): Promise<{
    totalConnections: number;
    feedbackGiven: number;
    pendingConnections: Array<{
      connectionId: string;
      otherUserName: string;
      connectedAt: Date;
    }>;
  }> {
    // Get user's connections at this event
    const connections = await this.prisma.connection.findMany({
      where: {
        eventId,
        OR: [{ userAId: userId }, { userBId: userId }],
      },
      include: {
        userA: { select: { firstName: true, lastName: true } },
        userB: { select: { firstName: true, lastName: true } },
      },
    });

    // Get feedback already given
    const feedback = await this.prisma.connectionFeedback.findMany({
      where: {
        userId,
        connectionId: { in: connections.map((c) => c.id) },
      },
      select: { connectionId: true },
    });

    const feedbackIds = new Set(feedback.map((f) => f.connectionId));

    // Find connections without feedback (older than 24 hours)
    const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const pendingConnections = connections
      .filter(
        (c) =>
          !feedbackIds.has(c.id) && new Date(c.connectedAt) < twentyFourHoursAgo,
      )
      .map((c) => {
        const otherUser = c.userAId === userId ? c.userB : c.userA;
        const otherUserName = `${otherUser.firstName || ''} ${otherUser.lastName || ''}`.trim() || 'Attendee';
        return {
          connectionId: c.id,
          otherUserName,
          connectedAt: c.connectedAt,
        };
      })
      .slice(0, 5); // Limit to 5 pending

    return {
      totalConnections: connections.length,
      feedbackGiven: feedback.length,
      pendingConnections,
    };
  }
}
