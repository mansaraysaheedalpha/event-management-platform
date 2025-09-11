import { gql } from "@apollo/client";

// --- Queries & Mutations for Events ---

export const GET_EVENTS_QUERY = gql`
  query GetEventsByOrganization {
    eventsByOrganization {
      id
      name
      status
      startDate
      endDate
      isPublic
    }
  }
`;

export const CREATE_EVENT_MUTATION = gql`
  mutation CreateEvent($input: EventCreateInput!) {
    createEvent(eventIn: $input) {
      id
      name
    }
  }
`;

export const GET_EVENT_DETAILS_QUERY = gql`
  query GetEventById($id: ID!) {
    event(id: $id) {
      id
      name
      description
      status
      startDate
      endDate
      isPublic
    }
  }
`;

// --- Queries & Mutations for Sessions ---

export const GET_SESSIONS_BY_EVENT_QUERY = gql`
  query GetSessionsByEvent($eventId: ID!) {
    sessionsByEvent(eventId: $eventId) {
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

export const CREATE_SESSION_MUTATION = gql`
  mutation CreateSession($input: SessionCreateInput!) {
    createSession(sessionIn: $input) {
      id
      title
    }
  }
`;

export const GET_REGISTRATIONS_BY_EVENT_QUERY = gql`
  query GetRegistrationsByEvent($eventId: ID!) {
    registrationsByEvent(eventId: $eventId) {
      id
      status
      ticketCode
      checkedInAt
      # Include details for both registered users and guests
      user {
        id
        firstName
        lastName
        email
      }
      guestEmail
      guestName
    }
  }
`;


export const CREATE_REGISTRATION_MUTATION = gql`
  mutation CreateRegistration($input: RegistrationCreateInput!) {
    createRegistration(registrationIn: $input) {
      id
      status
      user {
        id
        email
      }
      guestEmail
    }
  }
`;