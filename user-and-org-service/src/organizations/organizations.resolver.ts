// src/organizations/organizations.resolver.ts
import { Resolver, Query, Context, Mutation, Args, ID } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { GqlAuthGuard } from 'src/auth/guards/gql-auth.guard';
import { OrganizationsService } from './organizations.service';
import { InvitationsService } from 'src/invitations/invitations.service';

// Combined imports for cleaner code
import { DeleteOrganizationPayload, OrganizationMember, Role } from './gql_types/organization.types';
import {
  CreateInvitationInput,
  OnboardingCreateOrganizationInput,
  UpdateMemberRoleInput,
  UpdateOrganizationInput,
} from './gql_types/organization.inputs';
import { Organization, DeleteOrganizationInput } from './gql_types';
import { AuthPayload } from 'src/auth/gql_types/auth.types';
import { Response } from 'express';

@Resolver()
export class OrganizationResolver {
  constructor(
    private orgService: OrganizationsService,
    private invitationService: InvitationsService,
  ) {}

  @Query(() => [Organization])
  @UseGuards(GqlAuthGuard)
  async myOrganizations(
    @Context() context: { req: { user: { sub: string } } },
  ) {
    const userId = context.req.user.sub;
    return this.orgService.userOrganizations(userId);
  }

  @Query(() => [OrganizationMember])
  @UseGuards(GqlAuthGuard)
  async organizationMembers(
    @Context() context: { req: { user: { orgId: string } } },
  ) {
    const organizationId = context.req.user.orgId;
    return this.orgService.listMembers(organizationId);
  }

  @Query(() => [Role])
  @UseGuards(GqlAuthGuard)
  async listRolesForOrg(
    @Context() context: { req: { user: { orgId: string } } },
  ) {
    return this.orgService.getRoles(context.req.user.orgId);
  }

  @Mutation(() => String)
  @UseGuards(GqlAuthGuard)
  async createInvitation(
    @Args('input') createInvitationInput: CreateInvitationInput,
    @Context() context: { req: { user: { sub: string; orgId: string } } },
  ): Promise<string> {
    const invitedById = context.req.user.sub;
    const organizationId = context.req.user.orgId;

    const { message } = await this.invitationService.create({
      ...createInvitationInput,
      organizationId,
      invitedById,
    });
    return message;
  }

  @Mutation(() => OrganizationMember)
  @UseGuards(GqlAuthGuard)
  async updateMemberRole(
    @Args('input') updateMemberRoleInput: UpdateMemberRoleInput,
    @Context() context: { req: { user: { sub: string; orgId: string } } },
  ) {
    const actingUserId = context.req.user.sub;
    const organizationId = context.req.user.orgId;
    return this.orgService.updateMemberRole(
      organizationId,
      updateMemberRoleInput.memberId,
      updateMemberRoleInput.roleId,
      actingUserId,
    );
  }

  @Mutation(() => OrganizationMember) // Added back the removeMember mutation
  @UseGuards(GqlAuthGuard)
  async removeMember(
    @Args('memberId', { type: () => ID }) memberId: string,
    @Context() context: { req: { user: { sub: string; orgId: string } } },
  ): Promise<any> {
    const actingUserId = context.req.user.sub;
    const organizationId = context.req.user.orgId;
    return this.orgService.removeMember(organizationId, memberId, actingUserId);
  }

  @Query(() => Organization, { name: 'organization' })
  @UseGuards(GqlAuthGuard)
  async getOrganizationById(
    @Args('id', { type: () => ID }) id: string,
    @Context() context: { req: { user: { sub: string } } }, // <-- Get user from context
  ) {
    const userId = context.req.user.sub; // <-- Extract the userId
    return this.orgService.findOrgForUser(id, userId); // <-- Call the new secure method
  }

  @Mutation(() => DeleteOrganizationPayload) // <-- CHANGE THIS RETURN TYPE
  @UseGuards(GqlAuthGuard)
  async deleteOrganization(
    @Args('input') input: DeleteOrganizationInput,
    @Context() context: { req: { user: { sub: string } } },
  ) {
    const userId = context.req.user.sub;
    return this.orgService.deleteOrg(input.organizationId, userId, input.force);
  }

  @Mutation(() => Organization)
  @UseGuards(GqlAuthGuard)
  async restoreOrganization(
    @Args('organizationId', { type: () => ID }) organizationId: string,
    @Context() context: { req: { user: { sub: string } } },
  ) {
    const userId = context.req.user.sub;
    return this.orgService.restoreOrg(organizationId, userId);
  }

  // MUTATION 1: For the "orphaned user" onboarding flow. Returns full auth credentials.
  @Mutation(() => AuthPayload)
  @UseGuards(GqlAuthGuard)
  async onboardingCreateOrganization(
    @Args('input') input: OnboardingCreateOrganizationInput,
    @Context() context: { req: { user: { sub: string } }; res: Response },
  ) {
    const userId = context.req.user.sub;
    const { user, tokens } = await this.orgService.createNewOrganization(
      userId,
      { organization_name: input.name },
    );

    context.res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });

    return { token: tokens.access_token, user };
  }

  // MUTATION 2: For an already authenticated user creating an additional organization.
  // Returns a full AuthPayload to complete the session switch
  @Mutation(() => AuthPayload)
  @UseGuards(GqlAuthGuard)
  async createAdditionalOrganization(
    @Args('input') input: OnboardingCreateOrganizationInput,
    @Context() context: { req: { user: { sub: string } }; res: Response },
  ) {
    const userId = context.req.user.sub;
    const { user, tokens } = await this.orgService.createNewOrganization(
      userId,
      { organization_name: input.name },
    );

    // Set the new refresh token cookie
    context.res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });

    // Return the new access token and user
    return { token: tokens.access_token, user };
  }

  // ADD THIS MUTATION
  @Mutation(() => Organization)
  @UseGuards(GqlAuthGuard)
  async updateOrganization(
    @Args('input') input: UpdateOrganizationInput,
    @Context() context: { req: { user: { sub: string } } },
  ) {
    const userId = context.req.user.sub;
    return this.orgService.updateOrgDetails(
      input.organizationId,
      { name: input.name },
      userId,
    );
  }
}
