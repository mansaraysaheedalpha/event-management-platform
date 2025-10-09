// src/main.ts
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ValidationPipe } from '@nestjs/common';
import { Transport, KafkaOptions } from '@nestjs/microservices';
import { IoAdapter } from '@nestjs/platform-socket.io';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.enableCors({
    origin: ['http://localhost:3000'],
    credentials: true,
  });

  app.useWebSocketAdapter(new IoAdapter(app));

  // Connect to Kafka
  app.connectMicroservice<KafkaOptions>({
    transport: Transport.KAFKA,
    options: {
      client: {
        brokers: [process.env.KAFKA_BOOTSTRAP_SERVERS || 'kafka:29092'],
        // ✅ THE FIX IS HERE: Add a robust retry mechanism
        retry: {
          initialRetryTime: 300, // Start with a 300ms delay
          retries: 8, // Attempt to reconnect 8 times
        },
      },
      consumer: {
        // Ensure this matches the failing groupId from your logs
        groupId: 'real-time-consumer-server',
      },
    },
  });

  app.useGlobalPipes(new ValidationPipe());
  app.enableShutdownHooks();

  // Start microservices and the main application
  await app.startAllMicroservices();
  await app.listen(process.env.PORT ?? 3002);

  console.log(`🚀 Real-time service is running on: ${await app.getUrl()}`);
}
bootstrap();