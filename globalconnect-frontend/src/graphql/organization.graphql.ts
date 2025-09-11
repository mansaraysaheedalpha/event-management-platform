// src/graphql/organization.graphql.ts

import { gql } from "@apollo/client";

export const GET_MY_ORGS_QUERY = gql`
  query GetMyOrgs {
    myOrganizations {
      id
      name
    }
  }
`;

export const SWITCH_ORG_MUTATION = gql`
  mutation SwitchOrg($organizationId: ID!) {
    switchOrganization(organizationId: $organizationId) {
      token
      user {
        id
        email
        first_name
      }
    }
  }
`;

export const ONBOARDING_CREATE_ORGANIZATION_MUTATION = gql`
  mutation OnboardingCreateOrganization(
    $input: OnboardingCreateOrganizationInput!
  ) {
    onboardingCreateOrganization(input: $input) {
      token
      user {
        id
        first_name
        last_name
        email
      }
    }
  }
`;

// It's also a good idea to move other related mutations here
// to keep everything organized.
export const CREATE_ADDITIONAL_ORGANIZATION_MUTATION = gql`
  mutation CreateAdditionalOrganization(
    $input: OnboardingCreateOrganizationInput!
  ) {
    createAdditionalOrganization(input: $input) {
      token
      user {
        id
        first_name
        last_name
        email
      }
    }
  }
`;
