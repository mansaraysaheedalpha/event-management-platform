//src/internal/internal.module.ts
import { Module } from '@nestjs/common';
import { InternalController } from './internal.controller';
import { UsersModule } from 'src/users/users.module';

@Module({
  imports: [UsersModule],
  controllers: [InternalController],
})
export class InternalModule {}
