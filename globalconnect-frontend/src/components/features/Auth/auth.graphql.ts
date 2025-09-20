// src/components/features/Auth/auth.graphql.ts
import { gql } from "@apollo/client";

export const LOGIN_USER_MUTATION = gql`
  mutation Login($input: LoginInput!) {
    login(input: $input) {
      token
      user {
        id
        email
        first_name
      }
      requires2FA
      userIdFor2FA
    }
  }
`;


export const REGISTER_USER_MUTATION = gql`
  mutation RegisterUser($input: RegisterUserInput!) {
    registerUser(input: $input) {
      token
      user {
        id
        email
        first_name
      }
    }
  }
`;

export const LOGIN_2FA_MUTATION = gql`
  mutation Login2FA($input: Login2FAInput!) {
    login2FA(input: $input) {
      token
      user {
        id
        email
        first_name
      }
    }
  }
`;

export const LOGOUT_MUTATION = gql`
  mutation Logout {
    logout
  }
`;

export const CREATE_INVITATION_MUTATION = gql`
  mutation CreateInvitation($input: CreateInvitationInput!) {
    createInvitation(input: $input)
  }
`;

export const TEAM_DATA_QUERY = gql`
  query GetTeamData {
    organizationMembers {
      user {
        id
        first_name
        last_name
        email
      }
      role {
        id
        name
      }
    }
    listRolesForOrg {
      id
      name
    }
  }
`;

export const UPDATE_MEMBER_ROLE_MUTATION = gql`
  mutation UpdateMemberRole($input: UpdateMemberRoleInput!) {
    updateMemberRole(input: $input) {
      user {
        id
      }
      role {
        name
      }
    }
  }
`;

export const REMOVE_MEMBER_MUTATION = gql`
  mutation RemoveMember($memberId: ID!) {
    removeMember(memberId: $memberId) {
      user {
        id
      }
    }
  }
`;

export const GENERATE_2FA_MUTATION = gql`
  mutation Generate2FA {
    generate2FA {
      qrCodeDataUrl
    }
  }
`;

export const TURN_ON_2FA_MUTATION = gql`
  mutation TurnOn2FA($input: TurnOn2FAInput!) {
    turnOn2FA(input: $input)
  }
`;

export const PERFORM_PASSWORD_RESET_MUTATION = gql`
  mutation PerformPasswordReset($input: PerformResetInput!) {
    performPasswordReset(input: $input)
  }
`;