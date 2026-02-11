import { gql } from "@apollo/client";

export const GET_ORGANIZATION_SPEAKERS_QUERY = gql`
  query GetOrganizationSpeakers {
    organizationSpeakers {
      id
      name
      bio
      expertise
      userId
    }
  }
`;

export const CREATE_SPEAKER_MUTATION = gql`
  mutation CreateSpeaker($speakerIn: SpeakerCreateInput!) {
    createSpeaker(speakerIn: $speakerIn) {
      id
      name
      bio
      expertise
      userId
    }
  }
`;

export const UPDATE_SPEAKER_MUTATION = gql`
  mutation UpdateSpeaker($id: String!, $speakerIn: SpeakerUpdateInput!) {
    updateSpeaker(id: $id, speakerIn: $speakerIn) {
      id
      name
      bio
      expertise
      userId
    }
  }
`;

export const ARCHIVE_SPEAKER_MUTATION = gql`
  mutation ArchiveSpeaker($id: String!) {
    archiveSpeaker(id: $id) {
      id
    }
  }
`;
