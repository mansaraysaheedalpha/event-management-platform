import { gql } from "@apollo/client";

// This query fetches all registrations for a given event.
// It includes a federated 'user' field, which Apollo Gateway will resolve
// by fetching the user's details from the user-and-org-service.
// NOTE: This query requires organizer permissions (orgId in token)
export const GET_REGISTRATIONS_BY_EVENT_QUERY = gql`
  query GetRegistrationsByEvent($eventId: ID!) {
    registrationsByEvent(eventId: $eventId) {
      id
      status
      ticketCode
      checkedInAt
      guestEmail
      guestName
      user {
        id
        first_name
        last_name
        email
      }
    }
  }
`;

// This query fetches attendees for an event - accessible to any registered attendee.
// Used for the DM feature to show other attendees.
export const GET_EVENT_ATTENDEES_QUERY = gql`
  query GetEventAttendees($eventId: ID!) {
    eventAttendees(eventId: $eventId) {
      id
      user {
        id
        first_name
        last_name
        email
        imageUrl
      }
    }
  }
`;
