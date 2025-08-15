//src/users/users.module.ts
import { Module } from '@nestjs/common';
import { PrismaModule } from 'src/prisma.module';
import { UsersService } from './users.service';
import { UsersController } from './users.controller';
import { JwtModule } from '@nestjs/jwt';
import { ConfigModule } from '@nestjs/config';

@Module({
  imports: [PrismaModule, JwtModule, ConfigModule],
  controllers: [UsersController],
  providers: [UsersService],
})
export class UsersModule {}
