// src/common/guards/roles.guard.ts
import {
  Injectable,
  CanActivate,
  ExecutionContext,
  ForbiddenException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ROLES_KEY } from '../decorators/roles.decorator';
import { JwtPayload } from '../interfaces/auth.interface';

/**
 * Admin roles that have full access to analytics and management endpoints.
 */
const ADMIN_ROLES = ['admin', 'owner', 'organizer'];

/**
 * Permissions that grant analytics access.
 */
const ANALYTICS_PERMISSIONS = [
  'analytics:view',
  'analytics:manage',
  'event:manage',
  'event:analytics',
];

/**
 * RolesGuard implements role-based access control (RBAC).
 *
 * This guard checks if the authenticated user has the required roles or permissions
 * to access a protected route. It must be used AFTER JwtAuthGuard.
 *
 * Authorization Logic:
 * 1. If no @Roles() decorator is present, access is granted
 * 2. If user has any of the required roles (via `role` field), access is granted
 * 3. If user has any of the required permissions (via `permissions` array), access is granted
 * 4. Admin roles always have access to analytics endpoints
 *
 * @example
 * @UseGuards(JwtAuthGuard, RolesGuard)
 * @Roles('admin', 'organizer')
 * @Get('analytics')
 * getAnalytics() {}
 */
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    // Get required roles from decorator metadata
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(
      ROLES_KEY,
      [context.getHandler(), context.getClass()],
    );

    // If no roles required, allow access
    if (!requiredRoles || requiredRoles.length === 0) {
      return true;
    }

    // Get user from request (set by JwtAuthGuard)
    const request = context.switchToHttp().getRequest();
    const user: JwtPayload = request.user;

    if (!user) {
      throw new ForbiddenException('User not authenticated');
    }

    // Check if user has required role
    const hasRole = this.checkUserRole(user, requiredRoles);
    if (hasRole) {
      return true;
    }

    // Check if user has required permission
    const hasPermission = this.checkUserPermissions(user, requiredRoles);
    if (hasPermission) {
      return true;
    }

    throw new ForbiddenException(
      'You do not have permission to access this resource',
    );
  }

  /**
   * Check if user's role matches any of the required roles.
   */
  private checkUserRole(user: JwtPayload, requiredRoles: string[]): boolean {
    if (!user.role) {
      return false;
    }

    const userRole = user.role.toLowerCase();

    // Check direct role match
    if (requiredRoles.some((role) => role.toLowerCase() === userRole)) {
      return true;
    }

    // Admin roles have implicit access to analytics
    if (
      ADMIN_ROLES.includes(userRole) &&
      requiredRoles.some((role) => ANALYTICS_PERMISSIONS.includes(role))
    ) {
      return true;
    }

    return false;
  }

  /**
   * Check if user has any of the required permissions.
   */
  private checkUserPermissions(
    user: JwtPayload,
    requiredRoles: string[],
  ): boolean {
    if (!user.permissions || user.permissions.length === 0) {
      return false;
    }

    return requiredRoles.some((required) =>
      user.permissions!.some(
        (permission) => permission.toLowerCase() === required.toLowerCase(),
      ),
    );
  }
}
