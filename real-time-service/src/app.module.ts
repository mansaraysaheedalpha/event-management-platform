
import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { APP_GUARD } from '@nestjs/core';
import { JwtModule } from '@nestjs/jwt';
import { ThrottlerModule } from '@nestjs/throttler';

// --- CONTROLLER & SERVICE ---
import { AppController } from './app.controller';
import { AppService } from './app.service';

// --- AUTH & GUARDS ---
import { AuthModule } from './common/auth';
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
import { TicketsModule } from './tickets/tickets.module';
import { HealthModule } from './health/health.module';
import { VirtualStageModule } from './virtual-stage/virtual-stage.module';

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
    PrismaModule.forRootAsync({
      imports: [ConfigModule],
      // FIX: Removed 'async' because there is no 'await' inside.
      useFactory: (configService: ConfigService) => {
        const databaseUrl =
          configService.get<string>('NODE_ENV') === 'test'
            ? configService.getOrThrow<string>('TEST_DATABASE_URL')
            : configService.getOrThrow<string>('DATABASE_URL');

        return {
          database: {
            url: databaseUrl,
          },
        };
      },
      inject: [ConfigService],
    }),
    AuthModule,
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
    TicketsModule,
    HealthModule,
    VirtualStageModule,
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
  controllers: [AppController],
  providers: [
    {
      provide: APP_GUARD,
      useClass: WsThrottlerGuard,
    },
    AppService,
    AppGateway, // The main connection handler
  ],
})
export class AppModule {}