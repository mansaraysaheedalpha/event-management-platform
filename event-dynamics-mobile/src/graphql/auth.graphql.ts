// src/components/features/Auth/auth.graphql.ts
import { gql } from "@apollo/client";

export const LOGIN_USER_MUTATION = gql`
  mutation Login($input: LoginInput!) {
    login(input: $input) {
      token
      onboardingToken
      user {
        id
        email
        first_name
        last_name
      }
      requires2FA
      userIdFor2FA
      isAttendee
      isSponsor
      sponsorCount
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

// Attendee registration (no organization required)
export const REGISTER_ATTENDEE_MUTATION = gql`
  mutation RegisterAttendee($input: RegisterAttendeeInput!) {
    registerAttendee(input: $input) {
      token
      user {
        id
        email
        first_name
        last_name
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

// Request email backup code for 2FA (when authenticator app unavailable)
export const SEND_2FA_EMAIL_CODE_MUTATION = gql`
  mutation Send2FAEmailBackupCode($input: Send2FAEmailCodeInput!) {
    send2FAEmailBackupCode(input: $input) {
      message
    }
  }
`;

// Login with email backup code instead of authenticator
export const LOGIN_2FA_WITH_EMAIL_MUTATION = gql`
  mutation Login2FAWithEmailCode($input: Login2FAEmailInput!) {
    login2FAWithEmailCode(input: $input) {
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