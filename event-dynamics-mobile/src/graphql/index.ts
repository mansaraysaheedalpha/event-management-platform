// Barrel file — re-export all GraphQL operations
// Some files have overlapping exports (same queries in auth.graphql vs security.graphql),
// so we use explicit re-exports where needed to avoid ambiguity.

export * from './events.graphql';
export * from './attendee.graphql';
export * from './public.graphql';
export * from './monetization.graphql';
export * from './payments.graphql';
export * from './user.graphql';
export * from './registrations.graphql';
export * from './speakers.graphql';
export * from './dashboard.graphql';
export * from './venues.graphql';
export * from './blueprints.graphql';

// Auth has GENERATE_2FA_MUTATION and TURN_ON_2FA_MUTATION which also exist in security.graphql
// We export auth as the canonical source for auth operations
export * from './auth.graphql';

// Organization has GET_MY_ORGS_QUERY which also exists in queries.ts
// We export organization as the canonical source
export * from './organization.graphql';

// Re-export security excluding duplicates
export { GET_MY_PROFILE_2FA_STATUS, TURN_OFF_2FA_MUTATION } from './security.graphql';

// Re-export queries excluding duplicates
export { GET_EVENTS_BY_ORGANIZATION_QUERY } from './queries';
