// src/magic-link/magic-link.module.ts
import { Module } from '@nestjs/common';
import { JwtModule } from '@nestjs/jwt';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { MagicLinkService } from './magic-link.service';
import { MagicLinkController } from './magic-link.controller';
import { PrismaModule } from 'src/prisma.module';
import { AuditModule } from 'src/audit/audit.module';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [
    PrismaModule,
    AuditModule,
    SharedModule, // Provides Redis client
    ConfigModule,
    JwtModule.registerAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        secret: configService.get<string>('JWT_SECRET'),
        signOptions: { expiresIn: '1d' },
      }),
      inject: [ConfigService],
    }),
  ],
  controllers: [MagicLinkController],
  providers: [MagicLinkService],
  exports: [MagicLinkService],
})
export class MagicLinkModule {}
