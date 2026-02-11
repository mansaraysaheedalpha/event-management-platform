//src/graphql/venues.graphql.ts
import { gql } from "@apollo/client";

export const GET_ORGANIZATION_VENUES_QUERY = gql`
  query GetOrganizationVenues {
    organizationVenues {
      id
      name
      address
    }
  }
`;

export const CREATE_VENUE_MUTATION = gql`
  mutation CreateVenue($venueIn: VenueCreateInput!) {
    createVenue(venueIn: $venueIn) {
      id
      name
      address
    }
  }
`;

export const UPDATE_VENUE_MUTATION = gql`
  mutation UpdateVenue($id: String!, $venueIn: VenueUpdateInput!) {
    updateVenue(id: $id, venueIn: $venueIn) {
      id
      name
      address
    }
  }
`;

export const ARCHIVE_VENUE_MUTATION = gql`
  mutation ArchiveVenue($id: String!) {
    archiveVenue(id: $id) {
      id
    }
  }
`;
