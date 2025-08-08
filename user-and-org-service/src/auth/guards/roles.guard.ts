// In src/auth/guards/roles.guard.ts
import {
  CanActivate,
  ExecutionContext,
  Injectable,
  ForbiddenException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ROLES_KEY } from '../decorators/roles.decorator';
import { PrismaService } from 'src/prisma.service';
import { Request } from 'express';

// Define the shape of our user payload once
interface UserPayload {
  sub: string;
  email: string;
}

// Define the shape of a request that might contain an organizationId
interface RequestWithOrgId extends Request {
  body: {
    organizationId?: string;
  };
  query: {
    organizationId?: string;
  };
  params: {
    orgId?: string;
  };
  user?: UserPayload;
}

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(
    private readonly reflector: Reflector,
    private readonly prisma: PrismaService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const requiredRoles = this.reflector.get<string[]>(
      ROLES_KEY,
      context.getHandler(),
    );

    if (!requiredRoles || requiredRoles.length === 0) {
      return true;
    }

    const request = context.switchToHttp().getRequest<RequestWithOrgId>();
    const userId = request.user?.sub;
    const organizationId =
      request.params?.orgId ||
      request.body?.organizationId ||
      request.query?.organizationId;

    if (!userId || !organizationId) {
      throw new ForbiddenException(
        'User or Organization ID could not be determined from the request.',
      );
    }

    const membership = await this.prisma.membership.findUnique({
      where: {
        userId_organizationId: {
          userId,
          organizationId,
        },
      },
      include: {
        role: true,
      },
    });

    if (!membership) {
      throw new ForbiddenException(
        'You do not have access to this organization.',
      );
    }

    return requiredRoles.includes(membership.role.name);
  }
}
