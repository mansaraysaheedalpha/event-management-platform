//src/auth/auth.module.ts
import { forwardRef, Module } from '@nestjs/common';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { PrismaModule } from 'src/prisma.module';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { JwtModule } from '@nestjs/jwt';
import { RolesGuard } from './guards/roles.guard';
import { PassportModule } from '@nestjs/passport';
import { RefreshTokenStrategy } from './strategies/refresh-token.strategy';
import { AccessTokenStrategy } from './strategies/access-token.strategy';
import { InvitationsModule } from 'src/invitations/invitations.module';
import { TwoFactorModule } from 'src/two-factor/two-factor.module';
import { EmailModule } from 'src/email/email.module';
import { AuditModule } from 'src/audit/audit.module';
import { PermissionsModule } from 'src/permissions/permissions.module';
import { AuthResolver } from './auth.resolver';
import { UsersModule } from 'src/users/users.module';
import { OrganizationsModule } from 'src/organizations/organizations.module';

@Module({
  imports: [
    // Configuration for the JWT Module
    PrismaModule,
    PassportModule.register({ defaultStrategy: 'jwt' }),
    JwtModule.registerAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        secret: configService.get<string>('JWT_SECRET'), // Get the secret from .env
        signOptions: { expiresIn: '1d' }, // tokan lasts for a day
      }),
      inject: [ConfigService], // Inject the ConfigService
    }),
    InvitationsModule,
    EmailModule,
    TwoFactorModule,
    AuditModule,
    PermissionsModule,
    UsersModule,
    forwardRef(() => OrganizationsModule),
  ],
  controllers: [AuthController],
  providers: [
    AuthService,
    RefreshTokenStrategy,
    AccessTokenStrategy,
    RolesGuard,
    AuthResolver,
  ],
  exports: [RolesGuard, AuthService],
})
export class AuthModule {}
