//src/main.ts
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ConfigService } from '@nestjs/config';
import { ValidationPipe, Logger } from '@nestjs/common';
import helmet from 'helmet';
import * as cookieParser from 'cookie-parser';
import { Request, Response, NextFunction } from 'express';

async function bootstrap() {
  const logger = new Logger('Bootstrap');
  const app = await NestFactory.create(AppModule);
  const configService = app.get(ConfigService);

  // RAW health check endpoint - bypasses ALL NestJS guards including throttler
  // This MUST be registered before any other middleware
  app.use('/health', (req: Request, res: Response, next: NextFunction) => {
    if (req.method === 'GET') {
      res.status(200).json({
        status: 'ok',
        service: 'user-and-org-service',
        timestamp: new Date().toISOString()
      });
      return;
    }
    next();
  });

  // CORS Configuration from environment
  const allowedOrigins = configService.get<string>('ALLOWED_ORIGINS', '').split(',').filter(Boolean);
  app.enableCors({
    origin: allowedOrigins.length > 0 ? allowedOrigins : false,
    credentials: true,
  });

  app.use(helmet());
  app.use(cookieParser());

  const port = configService.get<number>('PORT', 3001);

  app.useGlobalPipes(new ValidationPipe({
    whitelist: true,
    forbidNonWhitelisted: true,
    transform: true,
  }));

  await app.listen(port, '0.0.0.0');
  logger.log(`Application is running on: ${await app.getUrl()}`);
}
bootstrap();
