import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../app.module';
import { PrismaService } from '../prisma.service';
import { AuthService } from '../auth/auth.service';

describe('UsersController (E2E)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let authService: AuthService;
  let accessToken: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    prisma = app.get<PrismaService>(PrismaService);
    authService = app.get<AuthService>(AuthService);
    
    app.useGlobalPipes(new ValidationPipe());
    await app.init();

    // Clean up and seed database
    await prisma.membership.deleteMany();
    await prisma.user.deleteMany();
    await prisma.role.deleteMany();
    await prisma.organization.deleteMany();
    
    // Create a user to test authenticated endpoints
    const registerDto = {
      organization_name: 'E2E User Org',
      first_name: 'E2E',
      last_name: 'User',
      email: 'e2e-user-test@example.com',
      password: 'password123',
    };
    await request(app.getHttpServer()).post('/users').send(registerDto);
    
    // Log the user in to get a token for other tests
    const loginRes = await request(app.getHttpServer()).post('/auth/login').send({
      email: registerDto.email,
      password: registerDto.password,
    });
    accessToken = loginRes.body.access_token;
  });

  afterAll(async () => {
    await app.close();
  });

  describe('/users (POST) - Registration', () => {
    it('should successfully register a new user and organization', () => {
      const registerDto = {
        organization_name: 'New Test Co.',
        first_name: 'New',
        last_name: 'User',
        email: 'new-user@example.com',
        password: 'password123',
      };
      return request(app.getHttpServer())
        .post('/users')
        .send(registerDto)
        .expect(201)
        .expect((res) => {
          expect(res.body.user).toHaveProperty('id');
          expect(res.body.user.email).toBe('new-user@example.com');
          expect(res.body.organization.name).toBe('New Test Co.');
        });
    });

    it('should return 409 Conflict if email already exists', () => {
      const registerDto = {
        organization_name: 'Duplicate Co.',
        first_name: 'Dupe',
        last_name: 'User',
        email: 'e2e-user-test@example.com', // This email already exists
        password: 'password123',
      };
      return request(app.getHttpServer())
        .post('/users')
        .send(registerDto)
        .expect(409);
    });
  });

  describe('/users/me (GET)', () => {
    it('should return the current user profile', () => {
      return request(app.getHttpServer())
        .get('/users/me')
        .set('Authorization', `Bearer ${accessToken}`)
        .expect(200)
        .expect((res) => {
          expect(res.body.email).toBe('e2e-user-test@example.com');
          expect(res.body).not.toHaveProperty('password');
        });
    });
  });

  describe('/users/me (PATCH)', () => {
    it('should update the user profile', () => {
      return request(app.getHttpServer())
        .patch('/users/me')
        .set('Authorization', `Bearer ${accessToken}`)
        .send({ first_name: 'UpdatedFirstName' })
        .expect(200)
        .expect({ message: 'User profile updated successfully' });
    });
  });

  describe('/users/me (GET) - with filter', () => {
    it('should return a formatted 404 error from the HttpExceptionFilter', () => {
      // Use a token for a user that we will delete
      const deletedUserToken = authService.getTokensForUser(
        { id: 'deleted-user', email: 'deleted@test.com' },
        { organizationId: 'org-1', role: { name: 'MEMBER' } },
      ).access_token;

      // Manually delete the user to guarantee a NotFoundException
      prisma.user.delete({ where: { id: 'deleted-user' } });

      return request(app.getHttpServer())
        .get('/users/me')
        .set('Authorization', `Bearer ${deletedUserToken}`)
        .expect(404)
        .expect((res) => {
          // Assert that the response body has the custom shape from our filter
          expect(res.body).toHaveProperty('statusCode', 404);
          expect(res.body).toHaveProperty('timestamp');
          expect(res.body).toHaveProperty('path', '/users/me');
          expect(res.body.message).toContain('not found');
        });
    });
  });
});
