// src/graphql/dashboard.graphql.ts
import { gql } from "@apollo/client";

// Core dashboard statistics query
export const GET_ORGANIZATION_DASHBOARD_STATS_QUERY = gql`
  query GetOrganizationDashboardStats {
    organizationDashboardStats {
      totalAttendees
      totalAttendeesChange
      activeSessions
      activeSessionsChange
      avgEngagementRate
      avgEngagementChange
      totalEvents
      totalEventsChange
    }
  }
`;

// Weekly attendance data for bar chart
export const GET_WEEKLY_ATTENDANCE_QUERY = gql`
  query GetWeeklyAttendance($days: Int) {
    weeklyAttendance(days: $days) {
      data {
        label
        date
        value
      }
    }
  }
`;

// Engagement trend for sparkline
export const GET_ENGAGEMENT_TREND_QUERY = gql`
  query GetEngagementTrend($periods: Int) {
    engagementTrend(periods: $periods) {
      data {
        period
        value
      }
    }
  }
`;

// Engagement breakdown (Q&A, Polls, Chat)
export const GET_ENGAGEMENT_BREAKDOWN_QUERY = gql`
  query GetEngagementBreakdown($eventId: ID) {
    engagementBreakdown(eventId: $eventId) {
      qaParticipation
      qaParticipationCount
      qaTotal
      pollResponseRate
      pollResponseCount
      pollTotal
      chatActivityRate
      chatMessageCount
      chatParticipants
      chatTotal
    }
  }
`;

// Combined dashboard query for efficiency (single request)
export const GET_DASHBOARD_DATA_QUERY = gql`
  query GetDashboardData {
    organizationDashboardStats {
      totalAttendees
      totalAttendeesChange
      activeSessions
      activeSessionsChange
      avgEngagementRate
      avgEngagementChange
      totalEvents
      totalEventsChange
    }
  }
`;

// Types for dashboard data
export interface DashboardStats {
  totalAttendees: number;
  totalAttendeesChange: number;
  activeSessions: number;
  activeSessionsChange: number;
  avgEngagementRate: number;
  avgEngagementChange: number;
  totalEvents: number;
  totalEventsChange: number;
}

export interface AttendanceDataPoint {
  label: string;
  date: string;
  value: number;
}

export interface EngagementTrendPoint {
  period: string;
  value: number;
}

export interface EngagementBreakdown {
  qaParticipation: number;
  qaParticipationCount: number;
  qaTotal: number;
  pollResponseRate: number;
  pollResponseCount: number;
  pollTotal: number;
  chatActivityRate: number;
  chatMessageCount: number;
  chatParticipants: number;
  chatTotal: number;
}

export interface DashboardData {
  organizationDashboardStats: DashboardStats;
}

// ==================== Virtual Attendance Analytics ====================

// Get virtual attendance stats for a specific event (organizer view)
export const GET_EVENT_VIRTUAL_ATTENDANCE_STATS_QUERY = gql`
  query GetEventVirtualAttendanceStats($eventId: ID!) {
    eventVirtualAttendanceStats(eventId: $eventId) {
      eventId
      totalViews
      uniqueViewers
      currentViewers
      avgWatchDurationSeconds
      sessionStats {
        sessionId
        totalViews
        uniqueViewers
        currentViewers
        avgWatchDurationSeconds
        peakViewers
      }
    }
  }
`;

// Types for virtual attendance
export interface VirtualAttendanceStats {
  sessionId: string;
  totalViews: number;
  uniqueViewers: number;
  currentViewers: number;
  avgWatchDurationSeconds: number;
  peakViewers: number;
}

export interface EventVirtualAttendanceStats {
  eventId: string;
  totalViews: number;
  uniqueViewers: number;
  currentViewers: number;
  avgWatchDurationSeconds: number;
  sessionStats: VirtualAttendanceStats[];
}
