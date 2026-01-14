import { Test, TestingModule } from '@nestjs/testing';
import { InvitationsService } from './invitations.service';
import { PrismaService } from '../prisma.service';
import { MailerService } from '@nestjs-modules/mailer';
import {
  UnauthorizedException,
  ConflictException,
  BadRequestException,
} from '@nestjs/common';

// Mock the Prisma client
const db = {
  role: {
    findUnique: jest.fn(),
    findFirst: jest.fn(),
  },
  invitation: {
    create: jest.fn(),
    findMany: jest.fn(),
    findUnique: jest.fn(),
    delete: jest.fn(),
  },
  user: {
    findUnique: jest.fn(),
    create: jest.fn(),
  },
  membership: {
    create: jest.fn(),
    findUnique: jest.fn(),
  },
  $transaction: jest.fn().mockImplementation((callback) => callback(db)),
};

describe('InvitationsService', () => {
  let service: InvitationsService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        InvitationsService,
        { provide: PrismaService, useValue: db },
        { provide: MailerService, useValue: { sendMail: jest.fn() } },
      ],
    }).compile();

    service = module.get<InvitationsService>(InvitationsService);
    // Clear all mock history before each test
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('create', () => {
    it('should create an invitation and send an email', async () => {
      // ARRANGE
      const roleData = { id: 'role_123', name: 'MEMBER' };
      db.role.findUnique.mockResolvedValue(roleData);
      db.invitation.create.mockResolvedValue({
        email: 'new-user@example.com',
        organization: { name: 'Test Org' },
        invitedBy: { first_name: 'Saheed', last_name: 'Alpha' },
      });

      // ACT
      const result = await service.create({
        email: 'new-user@example.com',
        role: 'MEMBER',
        organizationId: 'org_123',
        invitedById: 'user_123',
      });

      // ASSERT
      expect(db.role.findUnique).toHaveBeenCalled();
      expect(db.invitation.create).toHaveBeenCalled();
      expect(result.message).toContain('Invitation successfully sent');
    });
  });

  describe('accept', () => {
    it('should create a new user and membership when a valid token is accepted', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'invited@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        role: { id: 'role_123', name: 'MEMBER' },
        expiresAt: new Date(Date.now() + 1000 * 60 * 60), // Expires in 1 hour
      };
      const acceptDto = {
        first_name: 'Invited',
        last_name: 'User',
        password: 'password123',
      };

      // Mock the bcrypt.compare function, which we can't easily access
      const bcrypt = require('bcrypt');
      jest.spyOn(bcrypt, 'compare').mockResolvedValue(true);

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue(null); // Simulate user does not exist
      db.user.create.mockResolvedValue({ id: 'new_user_123', ...acceptDto });
      db.membership.create.mockResolvedValue({
        userId: 'new_user_123',
        organizationId: 'org_123',
      });

      // ACT
      const result = await service.accept('valid_raw_token', acceptDto);

      // ASSERT
      expect(result).toBeDefined();
      expect(result.user).toHaveProperty('id');
      expect(result.membership).toBeDefined();
      expect(db.user.create).toHaveBeenCalled();
      expect(db.membership.create).toHaveBeenCalled();
      expect(db.invitation.delete).toHaveBeenCalledWith({
        where: { id: mockInvitation.id },
      });
    });

    it('should throw an error for an invalid token', async () => {
      // ARRANGE
      db.invitation.findMany.mockResolvedValue([]); // No invitations found

      // ACT & ASSERT
      await expect(service.accept('invalid_token', {} as any)).rejects.toThrow(
        UnauthorizedException,
      );
    });
  });

  describe('preview', () => {
    it('should return invitation details with userExists=false for new users', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'new@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        expiresAt: new Date(Date.now() + 1000 * 60 * 60),
      };

      const bcrypt = require('bcrypt');
      jest.spyOn(bcrypt, 'compare').mockResolvedValue(true);

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue(null); // User does not exist
      db.invitation.findUnique.mockResolvedValue({
        ...mockInvitation,
        organization: { name: 'Test Org' },
        invitedBy: { first_name: 'John', last_name: 'Doe' },
        role: { name: 'MEMBER' },
      });

      // ACT
      const result = await service.preview('valid_token');

      // ASSERT
      expect(result.userExists).toBe(false);
      expect(result.email).toBe('new@example.com');
      expect(result.organizationName).toBe('Test Org');
      expect(result.existingUserFirstName).toBeUndefined();
    });

    it('should return invitation details with userExists=true for existing users', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'existing@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        expiresAt: new Date(Date.now() + 1000 * 60 * 60),
      };

      const bcrypt = require('bcrypt');
      jest.spyOn(bcrypt, 'compare').mockResolvedValue(true);

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue({ first_name: 'Jane' }); // User exists
      db.invitation.findUnique.mockResolvedValue({
        ...mockInvitation,
        organization: { name: 'Test Org' },
        invitedBy: { first_name: 'John', last_name: 'Doe' },
        role: { name: 'ADMIN' },
      });

      // ACT
      const result = await service.preview('valid_token');

      // ASSERT
      expect(result.userExists).toBe(true);
      expect(result.existingUserFirstName).toBe('Jane');
      expect(result.roleName).toBe('ADMIN');
    });
  });

  describe('acceptAsNewUser', () => {
    it('should create a new user and membership for new users', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'new@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        role: { id: 'role_123', name: 'MEMBER' },
        expiresAt: new Date(Date.now() + 1000 * 60 * 60),
      };
      const acceptDto = {
        first_name: 'New',
        last_name: 'User',
        password: 'SecurePass123!',
      };

      const bcrypt = require('bcrypt');
      jest.spyOn(bcrypt, 'compare').mockResolvedValue(true);

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue(null); // User does not exist
      db.user.create.mockResolvedValue({
        id: 'new_user_123',
        email: 'new@example.com',
        ...acceptDto,
      });
      db.membership.create.mockResolvedValue({
        userId: 'new_user_123',
        organizationId: 'org_123',
        role: { permissions: [] },
      });

      // ACT
      const result = await service.acceptAsNewUser('valid_token', acceptDto);

      // ASSERT
      expect(result.user).toBeDefined();
      expect(result.user.id).toBe('new_user_123');
      expect(db.user.create).toHaveBeenCalled();
      expect(db.membership.create).toHaveBeenCalled();
    });

    it('should throw ConflictException if user already exists', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'existing@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        expiresAt: new Date(Date.now() + 1000 * 60 * 60),
      };

      const bcrypt = require('bcrypt');
      jest.spyOn(bcrypt, 'compare').mockResolvedValue(true);

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue({ id: 'existing_user' }); // User exists

      // ACT & ASSERT
      await expect(
        service.acceptAsNewUser('valid_token', {
          first_name: 'Test',
          last_name: 'User',
          password: 'pass',
        }),
      ).rejects.toThrow(ConflictException);
    });
  });

  describe('acceptAsExistingUser', () => {
    it('should authenticate existing user and create membership', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'existing@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        expiresAt: new Date(Date.now() + 1000 * 60 * 60),
      };
      const existingUser = {
        id: 'existing_user_123',
        email: 'existing@example.com',
        first_name: 'Jane',
        last_name: 'Doe',
        password: '$2b$10$hashedpassword',
      };

      const bcrypt = require('bcrypt');
      jest
        .spyOn(bcrypt, 'compare')
        .mockResolvedValueOnce(true) // Token validation
        .mockResolvedValueOnce(true); // Password validation

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue(existingUser);
      db.membership.findUnique.mockResolvedValue(null); // Not already a member
      db.membership.create.mockResolvedValue({
        userId: 'existing_user_123',
        organizationId: 'org_123',
        role: { permissions: [] },
      });

      // ACT
      const result = await service.acceptAsExistingUser('valid_token', {
        password: 'correctPassword',
      });

      // ASSERT
      expect(result.user).toBeDefined();
      expect(result.user.id).toBe('existing_user_123');
      expect(db.membership.create).toHaveBeenCalled();
      expect(db.user.create).not.toHaveBeenCalled(); // Should NOT create new user
    });

    it('should throw UnauthorizedException for wrong password', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'existing@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        expiresAt: new Date(Date.now() + 1000 * 60 * 60),
      };
      const existingUser = {
        id: 'existing_user_123',
        email: 'existing@example.com',
        password: '$2b$10$hashedpassword',
      };

      const bcrypt = require('bcrypt');
      jest
        .spyOn(bcrypt, 'compare')
        .mockResolvedValueOnce(true) // Token validation
        .mockResolvedValueOnce(false); // Password validation fails

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue(existingUser);

      // ACT & ASSERT
      await expect(
        service.acceptAsExistingUser('valid_token', {
          password: 'wrongPassword',
        }),
      ).rejects.toThrow(UnauthorizedException);
    });

    it('should throw BadRequestException if user does not exist', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'new@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        expiresAt: new Date(Date.now() + 1000 * 60 * 60),
      };

      const bcrypt = require('bcrypt');
      jest.spyOn(bcrypt, 'compare').mockResolvedValue(true);

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue(null); // User does not exist

      // ACT & ASSERT
      await expect(
        service.acceptAsExistingUser('valid_token', { password: 'anyPassword' }),
      ).rejects.toThrow(BadRequestException);
    });

    it('should throw ConflictException if user is already a member', async () => {
      // ARRANGE
      const mockInvitation = {
        id: 'inv_123',
        token: '$2b$10$verylonghashedtoken',
        email: 'existing@example.com',
        organizationId: 'org_123',
        roleId: 'role_123',
        expiresAt: new Date(Date.now() + 1000 * 60 * 60),
      };
      const existingUser = {
        id: 'existing_user_123',
        email: 'existing@example.com',
        password: '$2b$10$hashedpassword',
      };

      const bcrypt = require('bcrypt');
      jest
        .spyOn(bcrypt, 'compare')
        .mockResolvedValueOnce(true) // Token validation
        .mockResolvedValueOnce(true); // Password validation

      db.invitation.findMany.mockResolvedValue([mockInvitation]);
      db.user.findUnique.mockResolvedValue(existingUser);
      db.membership.findUnique.mockResolvedValue({
        userId: 'existing_user_123',
        organizationId: 'org_123',
      }); // Already a member

      // ACT & ASSERT
      await expect(
        service.acceptAsExistingUser('valid_token', {
          password: 'correctPassword',
        }),
      ).rejects.toThrow(ConflictException);
    });
  });
});
