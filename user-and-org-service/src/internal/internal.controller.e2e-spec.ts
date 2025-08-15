import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../app.module';
import { PrismaService } from '../prisma.service';
import { ConfigService } from '@nestjs/config';

describe('InternalController (E2E)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let configService: ConfigService;
  let internalApiKey: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    prisma = app.get<PrismaService>(PrismaService);
    configService = app.get<ConfigService>(ConfigService);
    internalApiKey = configService.get<string>('INTERNAL_API_KEY');

    await app.init();

    // Seed a user for the test
    await prisma.user.deleteMany({
      where: { email: 'internal-test@example.com' },
    });
    await prisma.user.create({
      data: {
        id: 'internal-user-1',
        email: 'internal-test@example.com',
        password: 'password',
      },
    });
  });

  afterAll(async () => {
    await app.close();
  });

  describe('/internal/users/:id (GET)', () => {
    it('should return user data for a valid internal API key', () => {
      return request(app.getHttpServer())
        .get('/internal/users/internal-user-1')
        .set('x-internal-api-key', internalApiKey)
        .expect(200)
        .expect((res) => {
          expect(res.body.email).toBe('internal-test@example.com');
        });
    });

    it('should return 401 Unauthorized for a missing API key', () => {
      return request(app.getHttpServer())
        .get('/internal/users/internal-user-1')
        .expect(401);
    });

    it('should return 401 Unauthorized for an invalid API key', () => {
      return request(app.getHttpServer())
        .get('/internal/users/internal-user-1')
        .set('x-internal-api-key', 'invalid-key')
        .expect(401);
    });
  });
});
