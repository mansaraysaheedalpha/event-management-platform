import { gql } from "@apollo/client";

export const GET_SPEAKERS_BY_ORG_QUERY = gql`
  query GetSpeakersByOrg {
    # This query name must match a query defined in your backend resolvers
    # I'm assuming one will be created that returns all speakers for the user's org
    organizationSpeakers {
      id
      name
    }
  }
`;
