// src/app/(platform)/settings/_components/settings.graphql.ts
import { gql } from "@apollo/client";

// This is the query to get the current organization's data
export const GET_ORGANIZATION_QUERY = gql`
  query GetOrganization($organizationId: ID!) {
    organization(id: $organizationId) {
      id
      name
      status # <-- ADD THIS
      deletionScheduledAt # <-- AND ADD THIS
    }
  }
`;

export const UPDATE_ORGANIZATION_MUTATION = gql`
  mutation UpdateOrganization($input: UpdateOrganizationInput!) {
    updateOrganization(input: $input) {
      id
      name
    }
  }
`;


export const DELETE_ORGANIZATION_MUTATION = gql`
  mutation DeleteOrganization($input: DeleteOrganizationInput!) {
    deleteOrganization(input: $input) {
      success
      nextOrganizationId
    }
  }
`;

export const RESTORE_ORGANIZATION_MUTATION = gql`
  mutation RestoreOrganization($organizationId: ID!) {
    restoreOrganization(organizationId: $organizationId) {
      id
      status
    }
  }
`;
