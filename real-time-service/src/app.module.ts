//src/app.module.ts
import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { APP_GUARD } from '@nestjs/core';
import { JwtModule } from '@nestjs/jwt';
import { ThrottlerModule } from '@nestjs/throttler';

// --- GUARDS & MAIN GATEWAY ---
import { AppGateway } from './app.gateway';
import { WsThrottlerGuard } from './common/guards/ws-throttler.guard';

// --- FEATURE MODULES (which now only export services) ---
import { SharedModule } from './shared/shared.module';
import { CommModule } from './comm/comm.module';
import { LiveModule } from './live/live.module';
import { OpsModule } from './ops/ops.module';
import { MonetizationModule } from './monetization/ads/monetization.module';
import { GamificationModule } from './gamification/gamification.module';
import { NetworkingModule } from './networking/networking.module';
import { AlertsModule } from './alerts/alerts.module';
import { SystemModule } from './system/system.module';
import { PrismaModule } from './prisma.module';
import { GlobalModule } from './global/global.module';
import { ConnectionModule } from './system/connection/connection.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
    }),
    JwtModule.registerAsync({
      imports: [ConfigModule], // 1. Tell this setup it needs ConfigModule
      useFactory: (configService: ConfigService) => ({
        // The factory now receives configService as an argument
        secret: configService.get<string>('JWT_SECRET'),
      }),
      inject: [ConfigService], // 2. Explicitly inject the ConfigService
    }),
    PrismaModule,
    CommModule,
    SharedModule,
    LiveModule,
    OpsModule,
    MonetizationModule,
    GlobalModule,
    AlertsModule,
    SystemModule,
    GamificationModule,
    NetworkingModule,
    ConnectionModule,
    ThrottlerModule.forRoot([
      {
        name: 'default', // Name for the default tier
        ttl: 60000, // 60 seconds
        limit: 100, // 100 requests per minute
      },
      {
        name: 'vip', // Name for the VIP tier
        ttl: 60000,
        limit: 500, // 500 requests per minute
      },
    ]),
  ],
  providers: [
    {
      provide: APP_GUARD,
      useClass: WsThrottlerGuard,
    },
    AppGateway, // The main connection handler
  ],
})
export class AppModule {}
