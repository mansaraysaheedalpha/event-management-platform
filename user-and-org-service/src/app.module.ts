//src/app.module.ts
import { Module, MiddlewareConsumer, NestModule } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { AuthModule } from './auth/auth.module';
import { PrismaModule } from './prisma.module';
import { UsersModule } from './users/users.module';
import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler';
import { ThrottlerStorageRedisService } from '@nest-lab/throttler-storage-redis';
import { OrganizationsModule } from './organizations/organizations.module';
import { APP_FILTER, APP_GUARD } from '@nestjs/core';
import { AllExceptionsFilter } from './common/all-exceptions.filter';
import { InvitationsModule } from './invitations/invitations.module';
import { MailerModule } from '@nestjs-modules/mailer';
import { join } from 'path';
import { HandlebarsAdapter } from '@nestjs-modules/mailer/dist/adapters/handlebars.adapter';
import { TwoFactorModule } from './two-factor/two-factor.module';
import { AuditModule } from './audit/audit.module';
import { InternalModule } from './internal/internal.module';
import { EmailModule } from './email/email.module';
import { CsrfModule } from './common/csrf/csrf.module';
import { CsrfMiddleware } from './common/csrf/csrf.middleware';
import * as Joi from 'joi';
import { GraphQLModule } from '@nestjs/graphql';
import {
  ApolloFederationDriver,
  ApolloFederationDriverConfig,
} from '@nestjs/apollo';
import { Response } from 'express';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: process.env.NODE_ENV === 'test' ? '.env.test' : '.env',
      // Add this validation schema
      validationSchema: Joi.object({
        // Application
        NODE_ENV: Joi.string().valid('development', 'production', 'test').default('development'),
        PORT: Joi.number().default(3001),
        // Database
        DATABASE_URL: Joi.string().required(),
        REDIS_URL: Joi.string().required(),
        // Authentication
        JWT_SECRET: Joi.string().required(),
        JWT_REFRESH_SECRET: Joi.string().required(),
        // Security configuration
        INTERNAL_API_KEY: Joi.string().required(),
        ENCRYPTION_KEY: Joi.string().length(64).required(), // 32 bytes hex = 64 chars
        // URL configuration for emails and callbacks
        FRONTEND_URL: Joi.string().uri().required(),
        API_BASE_URL: Joi.string().uri().required(),
        // CORS configuration
        ALLOWED_ORIGINS: Joi.string().required(),
        // Resend email configuration
        RESEND_API_KEY: Joi.string().required(),
        RESEND_FROM_EMAIL: Joi.string().default('noreply@infinite-dynamics.com'),
        // Legacy SMTP config (kept for backward compatibility)
        MAIL_HOST: Joi.string().optional(),
        MAIL_PORT: Joi.number().optional(),
        MAIL_USER: Joi.string().optional(),
        MAIL_PASS: Joi.string().optional(),
        MAIL_FROM: Joi.string().optional(),
      }),
    }),
    AuthModule,
    PrismaModule,
    UsersModule,
    OrganizationsModule,
    ThrottlerModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        throttlers: [
          {
            name: 'default',
            ttl: 60000,
            limit: 100, // 100 requests per minute
          },
          {
            name: 'strict',
            ttl: 60000,
            limit: 10, // Stricter limit for sensitive endpoints like auth
          },
        ],
        storage: new ThrottlerStorageRedisService(
          configService.get<string>('REDIS_URL'),
        ),
      }),
      inject: [ConfigService],
    }),
    InvitationsModule,
    MailerModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        transport: {
          host: configService.get<string>('MAIL_HOST'),
          port: configService.get<number>('MAIL_PORT'),
          auth: {
            user: configService.get<string>('MAIL_USER'),
            pass: configService.get<string>('MAIL_PASS'),
          },
        },
        defaults: {
          from: `"No Reply" <${configService.get<string>('MAIL_FROM')}>`,
        },
        // This part is optional but good for making nice emails later
        template: {
          dir: join(__dirname, 'templates'),
          adapter: new HandlebarsAdapter(),
          options: {
            strict: true,
          },
        },
      }),
      inject: [ConfigService],
    }),
    TwoFactorModule,
    AuditModule,
    InternalModule,
    EmailModule,
    CsrfModule,
    GraphQLModule.forRoot<ApolloFederationDriverConfig>({
      driver: ApolloFederationDriver,
      autoSchemaFile: {
        federation: 2,
      },
      // playground: true, // This can be enabled for local development if needed
      context: ({ req, res }: { req: Request; res: Response }) => ({
        req,
        res,
      }),
    }),
  ],
  controllers: [AppController],
  providers: [
    AppService,
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,
    },
    {
      provide: APP_FILTER,
      useClass: AllExceptionsFilter,
    },
  ],
})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer) {
    // Apply CSRF middleware to GraphQL endpoint
    consumer.apply(CsrfMiddleware).forRoutes('graphql');
  }
}
