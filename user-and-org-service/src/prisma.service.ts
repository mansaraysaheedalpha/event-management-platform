//src/prisma.service
import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';

@Injectable()
export class PrismaService
  extends PrismaClient
  implements OnModuleInit, OnModuleDestroy
{
  async onModuleInit() {
    // This command connects to the database when the module is initialized.
    await this.$connect();
  }

  // **THE FIX**: This method is automatically called by NestJS when the app
  // shuts down, ensuring the database connection is gracefully closed.
  async onModuleDestroy() {
    await this.$disconnect();
  }
}
