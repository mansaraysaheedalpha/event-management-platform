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
