// In src/organizations/organizations.controller.ts

import {
  Controller,
  Post,
  Get,
  Param,
  Body,
  UseGuards,
  Req,
  Delete,
  HttpCode,
  Put,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { Roles } from 'src/auth/decorators/roles.decorator';
import { RolesGuard } from 'src/auth/guards/roles.guard';
import { Role } from '@prisma/client';
import { InvitationsService } from 'src/invitations/invitations.service';
import { CreateInvitationDto } from 'src/invitations/dto/CreateInvitationsDTO';
import { OrganizationsService } from './organizations.service';
import { UpdateMemberRoleDTO } from './dto/update-member-role.dto';
import { CreateNewOrganizationDTO } from './dto/create-new-organization.dto';
import { UpdateOrganizationDTO } from './dto/update-organization.dto';

@Controller('organizations')
export class OrganizationsController {
  constructor(
    private readonly invitationService: InvitationsService,
    private readonly orgService: OrganizationsService,
  ) {}

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Post(':orgId/invitations')
  @Roles('OWNER', 'ADMIN')
  async createInvitation(
    @Param('orgId') orgId: string,
    @Body() createInvitationDto: CreateInvitationDto,
    @Req() req: { user: { sub: string } },
  ) {
    const userId = req.user.sub;
    return await this.invitationService.create({
      ...createInvitationDto,
      organizationId: orgId,
      invitedById: userId,
    });
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Get(':orgId/members')
  @Roles('ADMIN', 'OWNER', 'MEMBER')
  async GetAllMembers(@Param('orgId') orgId: string) {
    return await this.orgService.listMembers(orgId);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Delete(':orgId/members/:memberId')
  @Roles('ADMIN', 'OWNER')
  @HttpCode(204)
  async RemoveAMember(
    @Req() req: { user: { sub: string } },
    @Param('orgId') orgId: string,
    @Param('memberId') memberToRemoveId: string,
  ) {
    const actingUserId = req.user.sub;
    return await this.orgService.removeMember(
      orgId,
      memberToRemoveId,
      actingUserId,
    );
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Put(':orgId/members/:userId/role')
  @Roles('OWNER')
  async UpdateRole(
    @Req() req: { user: { sub: string } },
    @Param('orgId') orgId: string,
    @Param('userId') userId: string,
    @Body() updateMemberRoleDto: UpdateMemberRoleDTO,
  ) {
    const actingUserId = req.user.sub;

    return await this.orgService.updateMemberRole(
      orgId,
      userId,
      updateMemberRoleDto.roleId,
      actingUserId,
    );
  }

  @UseGuards(AuthGuard('jwt'))
  @Get('/')
  async GetUserOrganizations(@Req() req: { user: { sub: string } }) {
    const userId = req.user.sub;
    return await this.orgService.userOrganizations(userId);
  }

  @UseGuards(AuthGuard('jwt'))
  @Post('/')
  async CreateNewOrganization(
    @Body() newOrgDto: CreateNewOrganizationDTO,
    @Req() req: { user: { sub: string } },
  ) {
    const userId = req.user.sub;
    return await this.orgService.createNewOrganization(userId, newOrgDto);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Get(':orgId')
  @Roles('ADMIN', 'OWNER', 'MEMBER')
  async FindOneOrg(@Param('orgId') orgId: string) {
    return await this.orgService.findOrg(orgId);
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Put(':orgId')
  @Roles('OWNER', 'ADMIN') // Also allow ADMINs to update details
  async UpdateOrg(
    @Param('orgId') orgId: string,
    @Body() updateOrgDto: UpdateOrganizationDTO,
    @Req() req: { user: { sub: string } }, // <-- Add this to get the user
  ) {
    const actingUserId = req.user.sub;
    return await this.orgService.updateOrgDetails(
      orgId,
      updateOrgDto,
      actingUserId,
    );
  }

  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Delete(':orgId')
  @Roles('OWNER')
  @HttpCode(204)
  async DeleteOrg(
    @Param('orgId') orgId: string,
    @Req() req: { user: { sub: string } }, // <-- Add this to get the user from the request
  ) {
    const actingUserId = req.user.sub; // <-- Extract the user's ID
    return await this.orgService.deleteOrg(orgId, actingUserId); // <-- Pass it to the service
  }

  @Get('restore/:token')
  async restoreOrganizationFromToken(@Param('token') token: string) {
    // This endpoint is public but protected by the single-use token
    return await this.orgService.restoreOrgFromToken(token);
  }
}
