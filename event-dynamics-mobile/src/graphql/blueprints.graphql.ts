import { gql } from "@apollo/client";

export const CREATE_BLUEPRINT_MUTATION = gql`
  mutation CreateBlueprint($blueprintIn: BlueprintCreateInput!) {
    createBlueprint(blueprintIn: $blueprintIn) {
      id
      name
    }
  }
`;

export const GET_ORGANIZATION_BLUEPRINTS_QUERY = gql`
  query GetOrganizationBlueprints {
    organizationBlueprints {
      id
      name
      description
      template
    }
  }
`;

export const INSTANTIATE_BLUEPRINT_MUTATION = gql`
  mutation InstantiateBlueprint(
    $id: String!
    $blueprintIn: InstantiateBlueprintInput!
  ) {
    instantiateBlueprint(id: $id, blueprintIn: $blueprintIn) {
      id
      name
    }
  }
`;