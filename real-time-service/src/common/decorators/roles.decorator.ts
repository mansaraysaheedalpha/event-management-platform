// src/common/decorators/roles.decorator.ts
import { SetMetadata } from '@nestjs/common';

/**
 * Metadata key for storing required roles/permissions on route handlers.
 */
export const ROLES_KEY = 'roles';

/**
 * Roles decorator for RBAC authorization.
 * Use with RolesGuard to restrict endpoint access.
 *
 * Can specify either:
 * - Role names (e.g., 'admin', 'organizer')
 * - Permission strings (e.g., 'event:manage', 'analytics:view')
 *
 * @example
 * // Require admin role
 * @Roles('admin')
 *
 * @example
 * // Require any of these permissions
 * @Roles('event:manage', 'analytics:view')
 */
export const Roles = (...roles: string[]) => SetMetadata(ROLES_KEY, roles);
