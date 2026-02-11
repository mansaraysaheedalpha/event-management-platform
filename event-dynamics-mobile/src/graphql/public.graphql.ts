//app/graphql/public.graphql.ts
import { gql } from "@apollo/client";

// Check if current user is already registered for an event (for authenticated users)
export const CHECK_EXISTING_REGISTRATION_QUERY = gql`
  query CheckExistingRegistration($eventId: ID!) {
    myRegistrationForEvent(eventId: $eventId) {
      id
      status
      ticketCode
      checkedInAt
    }
  }
`;

export const CREATE_REGISTRATION_MUTATION = gql`
  mutation CreateRegistration(
    $registrationIn: RegistrationCreateInput!
    $eventId: String!
  ) {
    createRegistration(registrationIn: $registrationIn, eventId: $eventId) {
      id
      status
      ticketCode
    }
  }
`;

export const GET_PUBLIC_EVENTS_QUERY = gql`
  query GetPublicEvents($limit: Int, $offset: Int, $includePast: Boolean) {
    publicEvents(limit: $limit, offset: $offset, includePast: $includePast) {
      totalCount
      events {
        id
        name
        description
        startDate
        endDate
        imageUrl
        isSoldOut
        venue {
          id
          name
        }
      }
    }
  }
`;

export const GET_PUBLIC_EVENT_DETAILS_QUERY = gql`
  query GetPublicEventDetails($eventId: ID!) {
    event(id: $eventId) {
      id
      name
      description
      startDate
      endDate
      imageUrl
      maxAttendees
      registrationsCount
      isSoldOut
      availableSpots
      venue {
        id
        name
      }
    }
    publicSessionsByEvent(eventId: $eventId) {
      id
      title
      startTime
      endTime
      speakers {
        id
        name
      }
    }
  }
`;

// Platform-wide statistics for marketing display (public, no auth required)
export const GET_PLATFORM_STATS_QUERY = gql`
  query GetPlatformStats {
    platformStats {
      totalEvents
      totalAttendees
      totalOrganizations
      uptimePercentage
    }
  }
`;
