/* eslint-disable */
import * as types from './graphql';
import { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';

/**
 * Map of all GraphQL operations in the project.
 *
 * This map has several performance disadvantages:
 * 1. It is not tree-shakeable, so it will include all operations in the project.
 * 2. It is not minifiable, so the string of a GraphQL query will be multiple times inside the bundle.
 * 3. It does not support dead code elimination, so it will add unused operations.
 *
 * Therefore it is highly recommended to use the babel or swc plugin for production.
 * Learn more about it here: https://the-guild.dev/graphql/codegen/plugins/presets/preset-client#reducing-bundle-size
 */
type Documents = {
    "\n  query GetOrganization($organizationId: ID!) {\n    organization(id: $organizationId) {\n      id\n      name\n      status # <-- ADD THIS\n      deletionScheduledAt # <-- AND ADD THIS\n    }\n  }\n": typeof types.GetOrganizationDocument,
    "\n  mutation UpdateOrganization($input: UpdateOrganizationInput!) {\n    updateOrganization(input: $input) {\n      id\n      name\n    }\n  }\n": typeof types.UpdateOrganizationDocument,
    "\n  mutation DeleteOrganization($input: DeleteOrganizationInput!) {\n    deleteOrganization(input: $input) {\n      success\n      nextOrganizationId\n    }\n  }\n": typeof types.DeleteOrganizationDocument,
    "\n  mutation RestoreOrganization($organizationId: ID!) {\n    restoreOrganization(organizationId: $organizationId) {\n      id\n      status\n    }\n  }\n": typeof types.RestoreOrganizationDocument,
    "\n  mutation RequestPasswordReset($input: RequestResetInput!) {\n    requestPasswordReset(input: $input)\n  }\n": typeof types.RequestPasswordResetDocument,
    "\n  mutation Login($input: LoginInput!) {\n    login(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n      requires2FA\n      userIdFor2FA\n    }\n  }\n": typeof types.LoginDocument,
    "\n  mutation RegisterUser($input: RegisterUserInput!) {\n    registerUser(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n": typeof types.RegisterUserDocument,
    "\n  mutation Login2FA($input: Login2FAInput!) {\n    login2FA(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n": typeof types.Login2FaDocument,
    "\n  mutation Logout {\n    logout\n  }\n": typeof types.LogoutDocument,
    "\n  mutation CreateInvitation($input: CreateInvitationInput!) {\n    createInvitation(input: $input)\n  }\n": typeof types.CreateInvitationDocument,
    "\n  query GetTeamData {\n    organizationMembers {\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n      role {\n        id\n        name\n      }\n    }\n    listRolesForOrg {\n      id\n      name\n    }\n  }\n": typeof types.GetTeamDataDocument,
    "\n  mutation UpdateMemberRole($input: UpdateMemberRoleInput!) {\n    updateMemberRole(input: $input) {\n      user {\n        id\n      }\n      role {\n        name\n      }\n    }\n  }\n": typeof types.UpdateMemberRoleDocument,
    "\n  mutation RemoveMember($memberId: ID!) {\n    removeMember(memberId: $memberId) {\n      user {\n        id\n      }\n    }\n  }\n": typeof types.RemoveMemberDocument,
    "\n  mutation Generate2FA {\n    generate2FA {\n      qrCodeDataUrl\n    }\n  }\n": typeof types.Generate2FaDocument,
    "\n  mutation TurnOn2FA($input: TurnOn2FAInput!) {\n    turnOn2FA(input: $input)\n  }\n": typeof types.TurnOn2FaDocument,
    "\n  mutation PerformPasswordReset($input: PerformResetInput!) {\n    performPasswordReset(input: $input)\n  }\n": typeof types.PerformPasswordResetDocument,
    "\n  mutation CreateAdditionalOrganization(\n    $input: OnboardingCreateOrganizationInput!\n  ) {\n    createAdditionalOrganization(input: $input) {\n      token\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n    }\n  }\n": typeof types.CreateAdditionalOrganizationDocument,
    "\n  query GetEventsByOrganization {\n    eventsByOrganization {\n      id\n      name\n      status\n      startDate # ✅ Changed start_date to startDate\n      endDate # ✅ Changed end_date to endDate\n      isPublic\n    }\n  }\n": typeof types.GetEventsByOrganizationDocument,
    "\n  mutation CreateEvent($input: EventCreateInput!) {\n    createEvent(eventIn: $input) {\n      id\n      name\n    }\n  }\n": typeof types.CreateEventDocument,
    "\n  query GetMyOrgs {\n    myOrganizations {\n      id\n      name\n    }\n  }\n": typeof types.GetMyOrgsDocument,
    "\n  mutation SwitchOrg($organizationId: ID!) {\n    switchOrganization(organizationId: $organizationId) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n": typeof types.SwitchOrgDocument,
    "\n  mutation OnboardingCreateOrganization(\n    $input: OnboardingCreateOrganizationInput!\n  ) {\n    onboardingCreateOrganization(input: $input) {\n      token\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n    }\n  }\n": typeof types.OnboardingCreateOrganizationDocument,
    "\n  query GetMyProfile2FA {\n    getMyProfile {\n      id\n      isTwoFactorEnabled\n    }\n  }\n": typeof types.GetMyProfile2FaDocument,
    "\n  mutation TurnOff2FA {\n    turnOff2FA\n  }\n": typeof types.TurnOff2FaDocument,
    "\n  query GetMyProfile {\n    getMyProfile {\n      id\n      first_name\n      last_name\n      email\n    }\n  }\n": typeof types.GetMyProfileDocument,
    "\n  mutation UpdateMyProfile($input: UpdateMyProfileInput!) {\n    updateMyProfile(input: $input) {\n      id\n      first_name\n      last_name\n    }\n  }\n": typeof types.UpdateMyProfileDocument,
    "\n  mutation ChangePassword($input: ChangePasswordInput!) {\n    changePassword(input: $input)\n  }\n": typeof types.ChangePasswordDocument,
};
const documents: Documents = {
    "\n  query GetOrganization($organizationId: ID!) {\n    organization(id: $organizationId) {\n      id\n      name\n      status # <-- ADD THIS\n      deletionScheduledAt # <-- AND ADD THIS\n    }\n  }\n": types.GetOrganizationDocument,
    "\n  mutation UpdateOrganization($input: UpdateOrganizationInput!) {\n    updateOrganization(input: $input) {\n      id\n      name\n    }\n  }\n": types.UpdateOrganizationDocument,
    "\n  mutation DeleteOrganization($input: DeleteOrganizationInput!) {\n    deleteOrganization(input: $input) {\n      success\n      nextOrganizationId\n    }\n  }\n": types.DeleteOrganizationDocument,
    "\n  mutation RestoreOrganization($organizationId: ID!) {\n    restoreOrganization(organizationId: $organizationId) {\n      id\n      status\n    }\n  }\n": types.RestoreOrganizationDocument,
    "\n  mutation RequestPasswordReset($input: RequestResetInput!) {\n    requestPasswordReset(input: $input)\n  }\n": types.RequestPasswordResetDocument,
    "\n  mutation Login($input: LoginInput!) {\n    login(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n      requires2FA\n      userIdFor2FA\n    }\n  }\n": types.LoginDocument,
    "\n  mutation RegisterUser($input: RegisterUserInput!) {\n    registerUser(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n": types.RegisterUserDocument,
    "\n  mutation Login2FA($input: Login2FAInput!) {\n    login2FA(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n": types.Login2FaDocument,
    "\n  mutation Logout {\n    logout\n  }\n": types.LogoutDocument,
    "\n  mutation CreateInvitation($input: CreateInvitationInput!) {\n    createInvitation(input: $input)\n  }\n": types.CreateInvitationDocument,
    "\n  query GetTeamData {\n    organizationMembers {\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n      role {\n        id\n        name\n      }\n    }\n    listRolesForOrg {\n      id\n      name\n    }\n  }\n": types.GetTeamDataDocument,
    "\n  mutation UpdateMemberRole($input: UpdateMemberRoleInput!) {\n    updateMemberRole(input: $input) {\n      user {\n        id\n      }\n      role {\n        name\n      }\n    }\n  }\n": types.UpdateMemberRoleDocument,
    "\n  mutation RemoveMember($memberId: ID!) {\n    removeMember(memberId: $memberId) {\n      user {\n        id\n      }\n    }\n  }\n": types.RemoveMemberDocument,
    "\n  mutation Generate2FA {\n    generate2FA {\n      qrCodeDataUrl\n    }\n  }\n": types.Generate2FaDocument,
    "\n  mutation TurnOn2FA($input: TurnOn2FAInput!) {\n    turnOn2FA(input: $input)\n  }\n": types.TurnOn2FaDocument,
    "\n  mutation PerformPasswordReset($input: PerformResetInput!) {\n    performPasswordReset(input: $input)\n  }\n": types.PerformPasswordResetDocument,
    "\n  mutation CreateAdditionalOrganization(\n    $input: OnboardingCreateOrganizationInput!\n  ) {\n    createAdditionalOrganization(input: $input) {\n      token\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n    }\n  }\n": types.CreateAdditionalOrganizationDocument,
    "\n  query GetEventsByOrganization {\n    eventsByOrganization {\n      id\n      name\n      status\n      startDate # ✅ Changed start_date to startDate\n      endDate # ✅ Changed end_date to endDate\n      isPublic\n    }\n  }\n": types.GetEventsByOrganizationDocument,
    "\n  mutation CreateEvent($input: EventCreateInput!) {\n    createEvent(eventIn: $input) {\n      id\n      name\n    }\n  }\n": types.CreateEventDocument,
    "\n  query GetMyOrgs {\n    myOrganizations {\n      id\n      name\n    }\n  }\n": types.GetMyOrgsDocument,
    "\n  mutation SwitchOrg($organizationId: ID!) {\n    switchOrganization(organizationId: $organizationId) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n": types.SwitchOrgDocument,
    "\n  mutation OnboardingCreateOrganization(\n    $input: OnboardingCreateOrganizationInput!\n  ) {\n    onboardingCreateOrganization(input: $input) {\n      token\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n    }\n  }\n": types.OnboardingCreateOrganizationDocument,
    "\n  query GetMyProfile2FA {\n    getMyProfile {\n      id\n      isTwoFactorEnabled\n    }\n  }\n": types.GetMyProfile2FaDocument,
    "\n  mutation TurnOff2FA {\n    turnOff2FA\n  }\n": types.TurnOff2FaDocument,
    "\n  query GetMyProfile {\n    getMyProfile {\n      id\n      first_name\n      last_name\n      email\n    }\n  }\n": types.GetMyProfileDocument,
    "\n  mutation UpdateMyProfile($input: UpdateMyProfileInput!) {\n    updateMyProfile(input: $input) {\n      id\n      first_name\n      last_name\n    }\n  }\n": types.UpdateMyProfileDocument,
    "\n  mutation ChangePassword($input: ChangePasswordInput!) {\n    changePassword(input: $input)\n  }\n": types.ChangePasswordDocument,
};

/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 *
 *
 * @example
 * ```ts
 * const query = gql(`query GetUser($id: ID!) { user(id: $id) { name } }`);
 * ```
 *
 * The query argument is unknown!
 * Please regenerate the types.
 */
export function gql(source: string): unknown;

/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query GetOrganization($organizationId: ID!) {\n    organization(id: $organizationId) {\n      id\n      name\n      status # <-- ADD THIS\n      deletionScheduledAt # <-- AND ADD THIS\n    }\n  }\n"): (typeof documents)["\n  query GetOrganization($organizationId: ID!) {\n    organization(id: $organizationId) {\n      id\n      name\n      status # <-- ADD THIS\n      deletionScheduledAt # <-- AND ADD THIS\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation UpdateOrganization($input: UpdateOrganizationInput!) {\n    updateOrganization(input: $input) {\n      id\n      name\n    }\n  }\n"): (typeof documents)["\n  mutation UpdateOrganization($input: UpdateOrganizationInput!) {\n    updateOrganization(input: $input) {\n      id\n      name\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation DeleteOrganization($input: DeleteOrganizationInput!) {\n    deleteOrganization(input: $input) {\n      success\n      nextOrganizationId\n    }\n  }\n"): (typeof documents)["\n  mutation DeleteOrganization($input: DeleteOrganizationInput!) {\n    deleteOrganization(input: $input) {\n      success\n      nextOrganizationId\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation RestoreOrganization($organizationId: ID!) {\n    restoreOrganization(organizationId: $organizationId) {\n      id\n      status\n    }\n  }\n"): (typeof documents)["\n  mutation RestoreOrganization($organizationId: ID!) {\n    restoreOrganization(organizationId: $organizationId) {\n      id\n      status\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation RequestPasswordReset($input: RequestResetInput!) {\n    requestPasswordReset(input: $input)\n  }\n"): (typeof documents)["\n  mutation RequestPasswordReset($input: RequestResetInput!) {\n    requestPasswordReset(input: $input)\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation Login($input: LoginInput!) {\n    login(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n      requires2FA\n      userIdFor2FA\n    }\n  }\n"): (typeof documents)["\n  mutation Login($input: LoginInput!) {\n    login(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n      requires2FA\n      userIdFor2FA\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation RegisterUser($input: RegisterUserInput!) {\n    registerUser(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation RegisterUser($input: RegisterUserInput!) {\n    registerUser(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation Login2FA($input: Login2FAInput!) {\n    login2FA(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation Login2FA($input: Login2FAInput!) {\n    login2FA(input: $input) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation Logout {\n    logout\n  }\n"): (typeof documents)["\n  mutation Logout {\n    logout\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation CreateInvitation($input: CreateInvitationInput!) {\n    createInvitation(input: $input)\n  }\n"): (typeof documents)["\n  mutation CreateInvitation($input: CreateInvitationInput!) {\n    createInvitation(input: $input)\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query GetTeamData {\n    organizationMembers {\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n      role {\n        id\n        name\n      }\n    }\n    listRolesForOrg {\n      id\n      name\n    }\n  }\n"): (typeof documents)["\n  query GetTeamData {\n    organizationMembers {\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n      role {\n        id\n        name\n      }\n    }\n    listRolesForOrg {\n      id\n      name\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation UpdateMemberRole($input: UpdateMemberRoleInput!) {\n    updateMemberRole(input: $input) {\n      user {\n        id\n      }\n      role {\n        name\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation UpdateMemberRole($input: UpdateMemberRoleInput!) {\n    updateMemberRole(input: $input) {\n      user {\n        id\n      }\n      role {\n        name\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation RemoveMember($memberId: ID!) {\n    removeMember(memberId: $memberId) {\n      user {\n        id\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation RemoveMember($memberId: ID!) {\n    removeMember(memberId: $memberId) {\n      user {\n        id\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation Generate2FA {\n    generate2FA {\n      qrCodeDataUrl\n    }\n  }\n"): (typeof documents)["\n  mutation Generate2FA {\n    generate2FA {\n      qrCodeDataUrl\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation TurnOn2FA($input: TurnOn2FAInput!) {\n    turnOn2FA(input: $input)\n  }\n"): (typeof documents)["\n  mutation TurnOn2FA($input: TurnOn2FAInput!) {\n    turnOn2FA(input: $input)\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation PerformPasswordReset($input: PerformResetInput!) {\n    performPasswordReset(input: $input)\n  }\n"): (typeof documents)["\n  mutation PerformPasswordReset($input: PerformResetInput!) {\n    performPasswordReset(input: $input)\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation CreateAdditionalOrganization(\n    $input: OnboardingCreateOrganizationInput!\n  ) {\n    createAdditionalOrganization(input: $input) {\n      token\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation CreateAdditionalOrganization(\n    $input: OnboardingCreateOrganizationInput!\n  ) {\n    createAdditionalOrganization(input: $input) {\n      token\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query GetEventsByOrganization {\n    eventsByOrganization {\n      id\n      name\n      status\n      startDate # ✅ Changed start_date to startDate\n      endDate # ✅ Changed end_date to endDate\n      isPublic\n    }\n  }\n"): (typeof documents)["\n  query GetEventsByOrganization {\n    eventsByOrganization {\n      id\n      name\n      status\n      startDate # ✅ Changed start_date to startDate\n      endDate # ✅ Changed end_date to endDate\n      isPublic\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation CreateEvent($input: EventCreateInput!) {\n    createEvent(eventIn: $input) {\n      id\n      name\n    }\n  }\n"): (typeof documents)["\n  mutation CreateEvent($input: EventCreateInput!) {\n    createEvent(eventIn: $input) {\n      id\n      name\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query GetMyOrgs {\n    myOrganizations {\n      id\n      name\n    }\n  }\n"): (typeof documents)["\n  query GetMyOrgs {\n    myOrganizations {\n      id\n      name\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation SwitchOrg($organizationId: ID!) {\n    switchOrganization(organizationId: $organizationId) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation SwitchOrg($organizationId: ID!) {\n    switchOrganization(organizationId: $organizationId) {\n      token\n      user {\n        id\n        email\n        first_name\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation OnboardingCreateOrganization(\n    $input: OnboardingCreateOrganizationInput!\n  ) {\n    onboardingCreateOrganization(input: $input) {\n      token\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation OnboardingCreateOrganization(\n    $input: OnboardingCreateOrganizationInput!\n  ) {\n    onboardingCreateOrganization(input: $input) {\n      token\n      user {\n        id\n        first_name\n        last_name\n        email\n      }\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query GetMyProfile2FA {\n    getMyProfile {\n      id\n      isTwoFactorEnabled\n    }\n  }\n"): (typeof documents)["\n  query GetMyProfile2FA {\n    getMyProfile {\n      id\n      isTwoFactorEnabled\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation TurnOff2FA {\n    turnOff2FA\n  }\n"): (typeof documents)["\n  mutation TurnOff2FA {\n    turnOff2FA\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  query GetMyProfile {\n    getMyProfile {\n      id\n      first_name\n      last_name\n      email\n    }\n  }\n"): (typeof documents)["\n  query GetMyProfile {\n    getMyProfile {\n      id\n      first_name\n      last_name\n      email\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation UpdateMyProfile($input: UpdateMyProfileInput!) {\n    updateMyProfile(input: $input) {\n      id\n      first_name\n      last_name\n    }\n  }\n"): (typeof documents)["\n  mutation UpdateMyProfile($input: UpdateMyProfileInput!) {\n    updateMyProfile(input: $input) {\n      id\n      first_name\n      last_name\n    }\n  }\n"];
/**
 * The gql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function gql(source: "\n  mutation ChangePassword($input: ChangePasswordInput!) {\n    changePassword(input: $input)\n  }\n"): (typeof documents)["\n  mutation ChangePassword($input: ChangePasswordInput!) {\n    changePassword(input: $input)\n  }\n"];

export function gql(source: string) {
  return (documents as any)[source] ?? {};
}

export type DocumentType<TDocumentNode extends DocumentNode<any, any>> = TDocumentNode extends DocumentNode<  infer TType,  any>  ? TType  : never;