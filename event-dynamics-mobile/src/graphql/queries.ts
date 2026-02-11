// src/graphql/queries.ts
import { gql } from "@apollo/client";

export const GET_MY_ORGS_QUERY = gql`
  query GetMyOrgs {
    myOrganizations {
      id
      name
    }
  }
`;

// Corrected query: Added variables for sorting.
export const GET_EVENTS_BY_ORGANIZATION_QUERY = gql`
  query GetEventsByOrganization(
    $limit: Int
    $offset: Int
    $sortBy: String
    $sortDirection: String
    $status: String
  ) {
    eventsByOrganization(
      limit: $limit
      offset: $offset
      sortBy: $sortBy
      sortDirection: $sortDirection
      status: $status
    ) {
      totalCount
      events {
        id
        name
        status
        startDate
        registrationsCount
        imageUrl
        eventType
      }
    }
  }
`;
