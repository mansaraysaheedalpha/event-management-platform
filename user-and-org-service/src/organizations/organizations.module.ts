import { forwardRef, Module } from '@nestjs/common';
import { OrganizationsController } from './organizations.controller';
import { AuthModule } from 'src/auth/auth.module';
import { PrismaModule } from 'src/prisma.module';
import { InvitationsModule } from 'src/invitations/invitations.module';
import { OrganizationsService } from './organizations.service';
import { AuditModule } from 'src/audit/audit.module';
import { OrganizationResolver, RoleResolver } from './organizations.resolver';
import { EmailModule } from 'src/email/email.module';

@Module({
  imports: [
    forwardRef(() => AuthModule),
    PrismaModule,
    InvitationsModule,
    AuditModule,
    EmailModule,
  ],
  controllers: [OrganizationsController],
  providers: [OrganizationsService, OrganizationResolver, RoleResolver],
  exports: [OrganizationsService],
})
export class OrganizationsModule {}
