// src/graphql/attendee.graphql.ts
import { gql } from "@apollo/client";

// Get all events the current user is registered for (attendee dashboard)
export const GET_MY_REGISTRATIONS_QUERY = gql`
  query GetMyRegistrations {
    myRegistrations {
      id
      status
      ticketCode
      checkedInAt
      event {
        id
        name
        description
        startDate
        endDate
        status
        imageUrl
        venue {
          id
          name
          address
        }
      }
    }
  }
`;

// Check if current user is registered for a specific event
export const GET_MY_REGISTRATION_FOR_EVENT_QUERY = gql`
  query GetMyRegistrationForEvent($eventId: ID!) {
    myRegistrationForEvent(eventId: $eventId) {
      id
      status
      ticketCode
      checkedInAt
      event {
        id
        name
        status
      }
    }
  }
`;

// Get attendee event details with sessions (includes session status and virtual fields)
export const GET_ATTENDEE_EVENT_DETAILS_QUERY = gql`
  query GetAttendeeEventDetails($eventId: ID!) {
    myRegistrationForEvent(eventId: $eventId) {
      id
      status
      ticketCode
      checkedInAt
    }
    event(id: $eventId) {
      id
      name
      description
      startDate
      endDate
      status
      imageUrl
      organizationId
      eventType
      virtualSettings {
        streamingProvider
        streamingUrl
        lobbyVideoUrl
        maxConcurrentViewers
      }
      venue {
        id
        name
        address
      }
    }
    publicSessionsByEvent(eventId: $eventId) {
      id
      title
      startTime
      endTime
      status
      chatEnabled
      qaEnabled
      pollsEnabled
      reactionsEnabled
      breakoutEnabled
      chatOpen
      qaOpen
      pollsOpen
      reactionsOpen
      sessionType
      streamingUrl
      recordingUrl
      broadcastOnly
      virtualRoomId
      streamingProvider
      isRecordable
      autoCaptions
      lobbyEnabled
      speakers {
        id
        name
        userId
      }
    }
  }
`;

// ==================== Virtual Attendance Mutations ====================

// Record when a user joins a virtual session
export const JOIN_VIRTUAL_SESSION_MUTATION = gql`
  mutation JoinVirtualSession($sessionId: String!, $deviceType: String, $userAgent: String) {
    joinVirtualSession(sessionId: $sessionId, deviceType: $deviceType, userAgent: $userAgent) {
      success
      message
      attendance {
        id
        userId
        sessionId
        eventId
        joinedAt
        leftAt
        watchDurationSeconds
        deviceType
      }
    }
  }
`;

// Record when a user leaves a virtual session
export const LEAVE_VIRTUAL_SESSION_MUTATION = gql`
  mutation LeaveVirtualSession($sessionId: String!) {
    leaveVirtualSession(sessionId: $sessionId) {
      success
      message
      watchDurationSeconds
      attendance {
        id
        userId
        sessionId
        eventId
        joinedAt
        leftAt
        watchDurationSeconds
        deviceType
      }
    }
  }
`;

// ==================== Virtual Attendance Queries ====================

// Get virtual attendance stats for a session
export const GET_VIRTUAL_ATTENDANCE_STATS_QUERY = gql`
  query GetVirtualAttendanceStats($sessionId: ID!) {
    virtualAttendanceStats(sessionId: $sessionId) {
      sessionId
      totalViews
      uniqueViewers
      currentViewers
      avgWatchDurationSeconds
      peakViewers
    }
  }
`;

// Get user's virtual attendance history for an event
export const GET_MY_VIRTUAL_ATTENDANCE_QUERY = gql`
  query GetMyVirtualAttendance($eventId: ID!) {
    myVirtualAttendance(eventId: $eventId) {
      id
      userId
      sessionId
      eventId
      joinedAt
      leftAt
      watchDurationSeconds
      deviceType
    }
  }
`;
