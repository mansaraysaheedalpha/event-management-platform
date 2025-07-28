import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { JwtModule } from '@nestjs/jwt';
import { PrismaModule } from './prisma.module';
import { CommModule } from './comm/comm.module';
import { SharedModule } from './shared/shared.module';
import { LiveModule } from './live/live.module';
import { EventEmitterModule } from '@nestjs/event-emitter';
import { OpsModule } from './ops/ops.module';
import { MonetizationModule } from './monetization/ads/monetization.module';
import { GlobalModule } from './global/global.module';
import { AlertsModule } from './alerts/alerts.module';
import { SystemModule } from './system/system.module';
import { GamificationModule } from './gamification/gamification.module';

@Module({
  imports: [
    EventEmitterModule.forRoot(),
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
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
