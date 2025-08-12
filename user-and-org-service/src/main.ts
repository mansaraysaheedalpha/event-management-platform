//src/main.ts
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ConfigService } from '@nestjs/config';
import { ValidationPipe } from '@nestjs/common';
import helmet from 'helmet';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';
import * as cookieParser from 'cookie-parser';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  // --- Add CORS Configuration ---
  app.enableCors({
    origin: [
      'http://localhost:3000', // Example for a React front-end
      'http://localhost:4200', // Example for an Angular front-end
      'http://localhost:5173', // Example for a Vue or Svelte front-end
    ],
    credentials: true, // Allows cookies to be sent
  });
  app.use(helmet());
  app.use(cookieParser());
  const configService = app.get(ConfigService);
  const port = configService.get<number>('PORT', 3000);

  app.useGlobalPipes(new ValidationPipe());
  app.useGlobalFilters(new HttpExceptionFilter());
  await app.listen(port);
  console.log(`Application is running on: ${await app.getUrl()}🚀`);
}
bootstrap();
