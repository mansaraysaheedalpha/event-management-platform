//src/users/users.service.ts
import {
  Injectable,
  ConflictException,
  NotFoundException,
  UnauthorizedException,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { RegisterUserDto } from './dto/register-user.dto';
import { PrismaService } from 'src/prisma.service';
import * as bcrypt from 'bcrypt';
import { UpdateProfileDTO } from './dto/update-profile.dto';
import { EmailService } from 'src/email/email.service';
import { randomBytes } from 'crypto';
import { User } from '@prisma/client';

@Injectable()
export class UsersService {
  private readonly logger = new Logger(UsersService.name);

  constructor(
    private prisma: PrismaService,
    private emailService: EmailService,
    private configService: ConfigService,
  ) {}
  async create(registerUserDto: RegisterUserDto) {
    const existingUser = await this.prisma.user.findUnique({
      where: { email: registerUserDto.email },
    });

    if (existingUser) {
      this.logger.warn('Registration attempt with existing email');
      throw new ConflictException('User with this email already exists');
    }

    // : Password hashing
    const saltRounds = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(
      registerUserDto.password,
      saltRounds,
    );

    const result = await this.prisma.$transaction(async (tx) => {
      const newOrg = await tx.organization.create({
        data: {
          name: registerUserDto.organization_name,
        },
      });

      const newUser = await tx.user.create({
        data: {
          email: registerUserDto.email,
          first_name: registerUserDto.first_name,
          last_name: registerUserDto.last_name,
          password: hashedPassword,
        },
      });

      const ownerRole = await tx.role.findFirst({
        where: { name: 'OWNER', isSystemRole: true },
      });
      if (!ownerRole)
        throw new Error(
          'System role OWNER not found. Please seed the database.',
        );

      await tx.membership.create({
        data: {
          userId: newUser.id,
          organizationId: newOrg.id,
          roleId: ownerRole.id,
        },
      });
      this.logger.log('Membership link created');

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { password, ...newUserToReturn } = newUser;

      return { user: newUserToReturn, organization: newOrg };
    });

    return result;
  }

  async findOne(id: string) {
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: id },
      // Select all the fields needed for the GqlUser type and security page
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
        isTwoFactorEnabled: true,
      },
    });

    return user;
  }

  async findOneByEmail(email: string) {
    const user = await this.prisma.user.findUnique({
      where: { email: email },
      // Ensure this select matches the GqlUser type
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
        isTwoFactorEnabled: true,
      },
    });

    if (!user) {
      throw new NotFoundException(`User with email ${email} not found`);
    }

    return user;
  }

  async updateProfile(userId: string, updateProfileDto: UpdateProfileDTO) {
    const data: { first_name?: string; last_name?: string } = {};
    if (
      updateProfileDto.first_name !== null &&
      updateProfileDto.first_name !== undefined
    ) {
      data.first_name = updateProfileDto.first_name;
    }
    if (
      updateProfileDto.last_name !== null &&
      updateProfileDto.last_name !== undefined
    ) {
      data.last_name = updateProfileDto.last_name;
    }

    const updatedUser = await this.prisma.user.update({
      where: { id: userId },
      data,
      // Select only the fields defined in our GqlUser type
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
      },
    });
    return updatedUser; // <-- Return the updated user object
  }

  async changePassword(
    userId: string,
    currentPassword: string,
    newPassword: string,
  ) {
    const userExists = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
    });

    const isPasswordMatch = await bcrypt.compare(
      currentPassword,
      userExists.password,
    );

    if (!isPasswordMatch) {
      throw new UnauthorizedException('wrong/invalid password');
    }

    const salt = await bcrypt.genSalt(10);
    const newHashedPassword = await bcrypt.hash(newPassword, salt);

    await this.prisma.user.update({
      where: { id: userId },
      data: {
        password: newHashedPassword,
      },
    });

    return { message: 'Successfully changed password' };
  }

  // STEP 1: User requests a change.
  async requestEmailChange(userId: string, newEmail: string) {
    // A. Get the user's current email
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
    });
    const oldEmail = user.email;

    // B. Create a secure, single-use token
    const rawToken = randomBytes(32).toString('hex');
    const hashedToken = await bcrypt.hash(rawToken, 10);
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000); // 15 min expiry

    // C. Store the token and the NEW email temporarily on the user's record
    await this.prisma.user.update({
      where: { id: userId },
      data: {
        newEmail,
        emailChangeToken: hashedToken,
        emailChangeTokenExpiresAt: expiresAt,
      },
    });

    // D. Send a verification email to the OLD address
    const verificationUrl = `${this.configService.get('API_BASE_URL')}/users/email-change/verify-old/${rawToken}`;
    await this.emailService.sendEmailChangeVerification(
      oldEmail,
      newEmail,
      verificationUrl,
    );

    return {
      message: 'Verification email sent to your current email address.',
    };
  }

  // STEP 2: User clicks the link in the OLD email.
  async confirmOldEmail(token: string) {
    // This is a more complex flow, so let's find the user in a more robust way
    const user = await this.findUserByEmailChangeToken(token);

    if (!user || !user.newEmail) {
      throw new UnauthorizedException('Invalid or expired token.');
    }

    // A. Generate a SECOND token for the NEW email address
    const finalRawToken = randomBytes(32).toString('hex');
    const finalHashedToken = await bcrypt.hash(finalRawToken, 10);

    // B. Update the token in the database
    await this.prisma.user.update({
      where: { id: user.id },
      data: {
        emailChangeToken: finalHashedToken,
        emailChangeTokenExpiresAt: new Date(Date.now() + 15 * 60 * 1000), // Reset expiry
      },
    });

    // C. Send the FINAL confirmation email to the NEW address
    const finalUrl = `${this.configService.get('API_BASE_URL')}/users/email-change/finalize/${finalRawToken}`;
    await this.emailService.sendEmailChangeFinal(user.newEmail, finalUrl);

    return {
      message:
        'Approval successful. A final confirmation link has been sent to your new email address.',
    };
  }

  // STEP 3: User clicks the link in the NEW email.
  async finalizeEmailChange(token: string) {
    const user = await this.findUserByEmailChangeToken(token);

    if (!user || !user.newEmail) {
      throw new UnauthorizedException('Invalid or expired token.');
    }

    // A. Final update: change the email and clear all temp fields
    await this.prisma.user.update({
      where: { id: user.id },
      data: {
        email: user.newEmail,
        newEmail: null,
        emailChangeToken: null,
        emailChangeTokenExpiresAt: null,
      },
    });

    return { message: 'Your email has been successfully updated.' };
  }

  // Helper method to reliably find a user by their token
  // Timing-safe: always iterate through ALL users without early exit
  private async findUserByEmailChangeToken(
    token: string,
  ): Promise<User | null> {
    const unexpiredUsers = await this.prisma.user.findMany({
      where: { emailChangeTokenExpiresAt: { gte: new Date() } },
    });

    let matchedUser: User | null = null;
    for (const user of unexpiredUsers) {
      if (user.emailChangeToken) {
        const isMatch = await bcrypt.compare(token, user.emailChangeToken);
        if (isMatch && !matchedUser) {
          matchedUser = user;
          // Continue iterating to prevent timing attacks
        }
      }
    }
    return matchedUser;
  }

  async findUserForInternal(userId: string) {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
      },
    });

    if (!user) {
      throw new NotFoundException('User not found.');
    }
    return user;
  }

  /**
   * Link a user to a sponsor by setting their sponsorId.
   * Called when a user accepts a sponsor invitation.
   * This enables sponsor permissions in their JWT token.
   */
  async linkUserToSponsor(userId: string, sponsorId: string) {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      throw new NotFoundException('User not found.');
    }

    const updatedUser = await this.prisma.user.update({
      where: { id: userId },
      data: { sponsorId },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        sponsorId: true,
      },
    });

    this.logger.log(`User ${userId} linked to sponsor ${sponsorId}`);
    return updatedUser;
  }

  /**
   * Remove a user's sponsor link.
   * Called when a user is removed from a sponsor team.
   */
  async unlinkUserFromSponsor(userId: string) {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      throw new NotFoundException('User not found.');
    }

    const updatedUser = await this.prisma.user.update({
      where: { id: userId },
      data: { sponsorId: null },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        sponsorId: true,
      },
    });

    this.logger.log(`User ${userId} unlinked from sponsor`);
    return updatedUser;
  }
}
