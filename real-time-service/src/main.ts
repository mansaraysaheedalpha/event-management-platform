// src/main.ts
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ValidationPipe } from '@nestjs/common';
import { Transport, KafkaOptions } from '@nestjs/microservices';
import { IoAdapter } from '@nestjs/platform-socket.io';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Get CORS origins from environment or default to localhost
  const allowedOrigins = process.env.ALLOWED_ORIGINS
    ? process.env.ALLOWED_ORIGINS.split(',').map((origin) => origin.trim())
    : ['http://localhost:3000'];

  app.enableCors({
    origin: allowedOrigins,
    credentials: true,
  });

  app.useWebSocketAdapter(new IoAdapter(app));

  // Build Kafka client configuration with optional SASL authentication
  const kafkaBrokers = (process.env.KAFKA_BOOTSTRAP_SERVERS || 'kafka:29092').split(',');
  const kafkaApiKey = process.env.KAFKA_API_KEY;
  const kafkaApiSecret = process.env.KAFKA_API_SECRET;

  const kafkaClientConfig: NonNullable<KafkaOptions['options']>['client'] = {
    brokers: kafkaBrokers,
    retry: {
      initialRetryTime: 300,
      retries: 8,
    },
  };

  // Add SASL/SSL authentication if credentials are provided (Confluent Cloud)
  if (kafkaApiKey && kafkaApiSecret) {
    kafkaClientConfig.ssl = true;
    kafkaClientConfig.sasl = {
      mechanism: 'plain' as const,
      username: kafkaApiKey,
      password: kafkaApiSecret,
    };
    console.log('Kafka microservice configured with SASL_SSL authentication');
  }

  // Connect to Kafka
  app.connectMicroservice<KafkaOptions>({
    transport: Transport.KAFKA,
    options: {
      client: kafkaClientConfig,
      consumer: {
        groupId: 'real-time-consumer-server',
      },
    },
  });

  app.useGlobalPipes(new ValidationPipe({ transform: true }));
  app.enableShutdownHooks();

  // Start microservices and the main application
  await app.startAllMicroservices();
  await app.listen(process.env.PORT ?? 3002);

  console.log(`Real-time service is running on: ${await app.getUrl()}`);
}
bootstrap();