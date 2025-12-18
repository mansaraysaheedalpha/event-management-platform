//src/invitations/invitations.module.ts
import { Module } from '@nestjs/common';
import { InvitationsService } from './invitations.service';
import { PrismaModule } from 'src/prisma.module';
import { JwtModule } from '@nestjs/jwt';
import { ConfigModule } from '@nestjs/config';
import { EmailModule } from 'src/email/email.module';

@Module({
  imports: [PrismaModule, JwtModule, ConfigModule, EmailModule],
  providers: [InvitationsService],
  exports: [InvitationsService],
})
export class InvitationsModule {}
