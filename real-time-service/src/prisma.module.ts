// src/prisma/prisma.module.ts

import { DynamicModule, Global, Module } from '@nestjs/common';
import { PrismaService } from './prisma.service';
import { ConfigService } from '@nestjs/config';

@Global()
@Module({})
export class PrismaModule {
  // This is the new dynamic method
  static forRootAsync(options: {
    imports: any[];
    useFactory: (
      configService: ConfigService,
    ) => Promise<{ database: { url: string } }> | { database: { url: string } };
    inject: any[];
  }): DynamicModule {
    return {
      module: PrismaModule,
      imports: options.imports,
      providers: [
        {
          provide: 'PRISMA_OPTIONS', // A temporary token
          useFactory: options.useFactory,
          inject: options.inject,
        },
        {
          provide: PrismaService,
          useFactory: (prismaOptions: { database: { url: string } }) => {
            // This is where we override the environment variable for PrismaClient
            process.env.DATABASE_URL = prismaOptions.database.url;
            return new PrismaService();
          },
          inject: ['PRISMA_OPTIONS'],
        },
      ],
      exports: [PrismaService],
    };
  }
}
