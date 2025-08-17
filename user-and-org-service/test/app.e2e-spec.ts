import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma.service';

describe('User & Org Service (E2E)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  jest.setTimeout(30000);

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    prisma = app.get<PrismaService>(PrismaService);

    app.useGlobalPipes(new ValidationPipe());
    await app.init();

    await prisma.membership.deleteMany();
    await prisma.user.deleteMany();
    await prisma.role.deleteMany();
    await prisma.organization.deleteMany();

    await prisma.role.create({
      data: {
        name: 'OWNER',
        isSystemRole: true,
      },
    });
  });

  afterAll(async () => {
    // Now that PrismaService has onModuleDestroy, this is all we need.
    await app.close();
  });

  describe('User Registration and Login Flow', () => {
    const newUser = {
      organization_name: 'E2E Test Corp',
      first_name: 'E2E',
      last_name: 'User',
      email: 'e2e@example.com',
      password: 'StrongPassword123!',
    };

    it('/users (POST) - should successfully register a new user and organization', () => {
      return request(app.getHttpServer())
        .post('/users')
        .send(newUser)
        .expect(201);
    });

    it('/users (POST) - should fail to register the same user twice', () => {
      return request(app.getHttpServer())
        .post('/users')
        .send(newUser)
        .expect(409);
    });

    it('/auth/login (POST) - should successfully log in the new user', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: newUser.email, password: newUser.password })
        .expect(201);
    });

    it('/auth/login (POST) - should fail to log in with the wrong password', () => {
      return request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: newUser.email, password: 'wrongpassword' })
        .expect(401);
    });
  });
});
