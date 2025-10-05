//src/main.ts
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ValidationPipe } from '@nestjs/common';
import { Transport, KafkaOptions } from '@nestjs/microservices';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Connect to Kafka
  app.connectMicroservice<KafkaOptions>({
    transport: Transport.KAFKA,
    options: {
      client: {
        brokers: [process.env.KAFKA_BOOTSTRAP_SERVERS || 'kafka:29092'],
      },
      consumer: {
        groupId: 'real-time-consumer',
      },
    },
  });

  app.useGlobalPipes(new ValidationPipe());

  // Start microservices and the main application
  await app.startAllMicroservices();
  await app.listen(process.env.PORT ?? 3002);

  console.log(`🚀 Real-time service is running on: ${await app.getUrl()}`);
}
bootstrap();
