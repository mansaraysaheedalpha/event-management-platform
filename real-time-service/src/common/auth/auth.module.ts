// src/common/auth/auth.module.ts
import { Module, Global } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { PassportModule } from '@nestjs/passport';
import { AccessTokenStrategy } from '../strategies/access-token.strategy';
import { JwtAuthGuard } from '../guards/jwt-auth.guard';

/**
 * Global authentication module providing JWT-based auth for REST endpoints.
 * Registers the Passport JWT strategy and exports the JwtAuthGuard.
 */
@Global()
@Module({
  imports: [
    ConfigModule,
    PassportModule.register({ defaultStrategy: 'jwt' }),
  ],
  providers: [AccessTokenStrategy, JwtAuthGuard],
  exports: [PassportModule, JwtAuthGuard],
})
export class AuthModule {}
