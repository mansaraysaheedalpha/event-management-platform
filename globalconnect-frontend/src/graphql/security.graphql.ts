// src/graphql/security.graphql.ts
import { gql } from "@apollo/client";

export const GET_MY_PROFILE_2FA_STATUS = gql`
  query GetMyProfile2FA {
    getMyProfile {
      id
      isTwoFactorEnabled
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
export const TURN_OFF_2FA_MUTATION = gql`
  mutation TurnOff2FA {
    turnOff2FA
  }
`;
