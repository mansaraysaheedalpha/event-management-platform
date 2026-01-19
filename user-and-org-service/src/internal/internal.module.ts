//src/internal/internal.module.ts
import { Module } from '@nestjs/common';
import { InternalController } from './internal.controller';
import { UsersModule } from 'src/users/users.module';
import { AuthModule } from 'src/auth/auth.module';
import { PrismaModule } from 'src/prisma.module';

@Module({
  imports: [UsersModule, AuthModule, PrismaModule],
  controllers: [InternalController],
})
export class InternalModule {}
