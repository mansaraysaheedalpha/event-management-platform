// src/graphql/user.graphql.ts
import { gql } from "@apollo/client";

export const GET_MY_PROFILE_QUERY = gql`
  query GetMyProfile {
    getMyProfile {
      id
      first_name
      last_name
      email
    }
  }
`;

export const UPDATE_MY_PROFILE_MUTATION = gql`
  mutation UpdateMyProfile($input: UpdateMyProfileInput!) {
    updateMyProfile(input: $input) {
      id
      first_name
      last_name
    }
  }
`;

export const CHANGE_PASSWORD_MUTATION = gql`
  mutation ChangePassword($input: ChangePasswordInput!) {
    changePassword(input: $input)
  }
`;
