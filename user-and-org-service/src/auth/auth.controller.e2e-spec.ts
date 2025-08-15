import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../app.module';
import { PrismaService } from '../prisma.service';
import * as bcrypt from 'bcrypt';
import * as cookieParser from 'cookie-parser';
import { User, Organization, Role } from '@prisma/client';

describe('AuthController (E2E)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let testUser: User;
  let testOrg: Organization;
  let testRole: Role;
  let accessToken: string;
  let refreshToken: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    prisma = app.get<PrismaService>(PrismaService);
    
    app.use(cookieParser());
    app.useGlobalPipes(new ValidationPipe());
    await app.init();

    // Clean up and seed database
    await prisma.membership.deleteMany();
    await prisma.user.deleteMany();
    await prisma.role.deleteMany();
    await prisma.organization.deleteMany();
    
    testOrg = await prisma.organization.create({ data: { name: 'E2E Test Org' } });
    testRole = await prisma.role.create({ data: { name: 'ADMIN', organizationId: testOrg.id } });
    const hashedPassword = await bcrypt.hash('password123', 10);
    testUser = await prisma.user.create({
      data: {
        email: 'e2e-auth-test@example.com',
        password: hashedPassword,
        first_name: 'E2E',
        last_name: 'Auth',
      },
    });
    await prisma.membership.create({
      data: { userId: testUser.id, organizationId: testOrg.id, roleId: testRole.id },
    });
  });

  afterAll(async () => {
    await app.close();
  });

  describe('/auth/login (POST)', () => {
    it('should return an access token and set a refresh token cookie', async () => {
      const res = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: 'e2e-auth-test@example.com', password: 'password123' })
        .expect(201);

      expect(res.body).toHaveProperty('access_token');
      const cookie = res.headers['set-cookie'][0];
      expect(cookie).toMatch(/refresh_token=.+/);
      
      // Store tokens for subsequent tests
      accessToken = res.body.access_token;
      refreshToken = cookie.split(';')[0].split('=')[1];
    });
  });

  describe('/auth/refresh (POST)', () => {
    it('should issue a new access token and refresh token', () => {
      return request(app.getHttpServer())
        .post('/auth/refresh')
        .set('Authorization', `Bearer ${refreshToken}`)
        .expect(201)
        .expect((res) => {
          expect(res.body).toHaveProperty('access_token');
          const cookie = res.headers['set-cookie'][0];
          expect(cookie).toMatch(/refresh_token=.+/);
        });
    });
  });
  
  describe('/auth/token/switch (POST)', () => {
    it('should issue new tokens for the specified organization', async () => {
      const newOrg = await prisma.organization.create({ data: { name: 'New Test Org' } });
      const newRole = await prisma.role.create({ data: { name: 'MEMBER', organizationId: newOrg.id } });
      await prisma.membership.create({ data: { userId: testUser.id, organizationId: newOrg.id, roleId: newRole.id } });

      return request(app.getHttpServer())
        .post('/auth/token/switch')
        .set('Authorization', `Bearer ${accessToken}`)
        .send({ organizationId: newOrg.id })
        .expect(201)
        .expect((res) => {
          expect(res.body).toHaveProperty('access_token');
          // We could decode the token here to verify the new orgId if needed
        });
    });
  });

  describe('/auth/logout (POST)', () => {
    it('should clear the refresh token and clear the cookie', async () => {
      const userBefore = await prisma.user.findUnique({ where: { id: testUser.id } });
      expect(userBefore.hashedRefreshToken).not.toBeNull();

      const res = await request(app.getHttpServer())
        .post('/auth/logout')
        .set('Authorization', `Bearer ${accessToken}`)
        .expect(200);

      const userAfter = await prisma.user.findUnique({ where: { id: testUser.id } });
      expect(userAfter.hashedRefreshToken).toBeNull();
      
      const cookie = res.headers['set-cookie'][0];
      expect(cookie).toContain('refresh_token=;'); // Check that the cookie is cleared
    });
  });
});