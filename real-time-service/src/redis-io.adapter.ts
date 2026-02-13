// src/redis-io.adapter.ts
import { IoAdapter } from '@nestjs/platform-socket.io';
import { ServerOptions } from 'socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import { Redis } from 'ioredis';
import { INestApplicationContext } from '@nestjs/common';

export class RedisIoAdapter extends IoAdapter {
  private adapterConstructor: ReturnType<typeof createAdapter>;

  constructor(app: INestApplicationContext, private readonly redisUrl: string) {
    super(app);
  }

  async connectToRedis(): Promise<void> {
    const pubClient = new Redis(this.redisUrl);
    const subClient = pubClient.duplicate();

    this.adapterConstructor = createAdapter(pubClient, subClient);

    return new Promise((resolve) => {
      pubClient.on('connect', () => {
        console.log('Socket.IO Redis adapter - Publisher connected');
      });
      subClient.on('connect', () => {
        console.log('Socket.IO Redis adapter - Subscriber connected');
        resolve();
      });
    });
  }

  createIOServer(port: number, options?: ServerOptions): any {
    const server = super.createIOServer(port, {
      ...options,
      // Increase max listeners to prevent memory leak warnings
      // Multiple gateways (AppGateway, ExpoGateway, etc.) add disconnect listeners
      maxHttpBufferSize: 1e8, // 100MB for large payloads
    });

    // Increase EventEmitter max listeners to 50 (default is 10)
    // This prevents "MaxListenersExceededWarning" when multiple gateways
    // attach listeners to the same socket
    server.sockets.setMaxListeners(50);

    server.adapter(this.adapterConstructor);
    console.log('Socket.IO Redis adapter enabled for horizontal scaling');
    return server;
  }
}
