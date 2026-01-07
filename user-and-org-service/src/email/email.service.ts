// src/email/email.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Resend } from 'resend';

interface SendEmailOptions {
  to: string;
  subject: string;
  html: string;
}

interface RetryConfig {
  maxRetries: number;
  baseDelayMs: number;
  maxDelayMs: number;
}

@Injectable()
export class EmailService {
  private readonly resend: Resend;
  private readonly fromEmail: string;
  private readonly logger = new Logger(EmailService.name);
  private readonly retryConfig: RetryConfig = {
    maxRetries: 3,
    baseDelayMs: 1000,
    maxDelayMs: 10000,
  };

  constructor(private readonly configService: ConfigService) {
    const apiKey = this.configService.get<string>('RESEND_API_KEY');
    if (!apiKey) {
      this.logger.warn('RESEND_API_KEY not configured. Emails will not be sent.');
    }
    this.resend = new Resend(apiKey);
    this.fromEmail = this.configService.get<string>('RESEND_FROM_EMAIL') || 'noreply@infinite-dynamics.com';
  }

  private async delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private calculateBackoff(attempt: number): number {
    // Exponential backoff with jitter: baseDelay * 2^attempt + random jitter
    const exponentialDelay = this.retryConfig.baseDelayMs * Math.pow(2, attempt);
    const jitter = Math.random() * 500; // Add up to 500ms jitter
    return Math.min(exponentialDelay + jitter, this.retryConfig.maxDelayMs);
  }

  private isRetryableError(error: { message?: string; statusCode?: number }): boolean {
    // Retry on rate limits (429), server errors (5xx), and network issues
    if (error.statusCode) {
      return error.statusCode === 429 || error.statusCode >= 500;
    }
    // Retry on common transient error messages
    const retryableMessages = ['ECONNRESET', 'ETIMEDOUT', 'ENOTFOUND', 'rate limit'];
    return retryableMessages.some((msg) =>
      error.message?.toLowerCase().includes(msg.toLowerCase())
    );
  }

  async sendEmail(options: SendEmailOptions): Promise<boolean> {
    let lastError: unknown;

    for (let attempt = 0; attempt <= this.retryConfig.maxRetries; attempt++) {
      try {
        const { data, error } = await this.resend.emails.send({
          from: `GlobalConnect <${this.fromEmail}>`,
          to: options.to,
          subject: options.subject,
          html: options.html,
        });

        if (error) {
          lastError = error;

          // Check if error is retryable
          if (attempt < this.retryConfig.maxRetries && this.isRetryableError(error)) {
            const backoffMs = this.calculateBackoff(attempt);
            this.logger.warn(
              `Email to ${options.to} failed (attempt ${attempt + 1}/${this.retryConfig.maxRetries + 1}): ${error.message}. Retrying in ${backoffMs}ms...`
            );
            await this.delay(backoffMs);
            continue;
          }

          this.logger.error(`Failed to send email to ${options.to} after ${attempt + 1} attempt(s): ${error.message}`);
          return false;
        }

        if (attempt > 0) {
          this.logger.log(`Email sent successfully to ${options.to} after ${attempt + 1} attempts, id: ${data?.id}`);
        } else {
          this.logger.log(`Email sent successfully to ${options.to}, id: ${data?.id}`);
        }
        return true;
      } catch (error) {
        lastError = error;

        // Check if error is retryable
        if (attempt < this.retryConfig.maxRetries && this.isRetryableError(error as { message?: string })) {
          const backoffMs = this.calculateBackoff(attempt);
          this.logger.warn(
            `Email to ${options.to} threw exception (attempt ${attempt + 1}/${this.retryConfig.maxRetries + 1}). Retrying in ${backoffMs}ms...`
          );
          await this.delay(backoffMs);
          continue;
        }

        this.logger.error(`Failed to send email to ${options.to} after ${attempt + 1} attempt(s):`, error);
        return false;
      }
    }

    this.logger.error(`Failed to send email to ${options.to} after all retry attempts:`, lastError);
    return false;
  }

  // Password Reset Email
  async sendPasswordResetEmail(
    to: string,
    firstName: string,
    resetUrl: string,
  ): Promise<boolean> {
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
      </head>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <h2 style="color: #18181b; margin: 0 0 24px 0; font-size: 24px;">Password Reset Request</h2>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">Hi ${firstName || 'there'},</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
              We received a request to reset your password for your <strong>GlobalConnect</strong> account.
            </p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
              Click the button below to set a new password:
            </p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="${resetUrl}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Reset My Password</a>
            </div>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 0 0 16px 0;">
              This link will expire in <strong>15 minutes</strong> for your security.
            </p>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 0;">
              If you didn't request a password reset, please ignore this email or contact support.
            </p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 14px; margin: 0;">— The GlobalConnect Team</p>
          </div>
        </div>
      </body>
      </html>
    `;

    return this.sendEmail({
      to,
      subject: 'Reset Your Password - GlobalConnect',
      html,
    });
  }

  // Email Change Verification (to old email)
  async sendEmailChangeVerification(
    to: string,
    newEmail: string,
    verificationUrl: string,
  ): Promise<boolean> {
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
      </head>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <h2 style="color: #18181b; margin: 0 0 24px 0; font-size: 24px;">Confirm Your Email Change Request</h2>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
              A request was made to change your email address to <strong>${newEmail}</strong>.
            </p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
              Click the button below to approve this change:
            </p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="${verificationUrl}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Approve Email Change</a>
            </div>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 0;">
              This link expires in <strong>15 minutes</strong>. If you didn't request this change, please ignore this email.
            </p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 14px; margin: 0;">— The GlobalConnect Team</p>
          </div>
        </div>
      </body>
      </html>
    `;

    return this.sendEmail({
      to,
      subject: 'Confirm Your Email Change Request - GlobalConnect',
      html,
    });
  }

  // Email Change Finalization (to new email)
  async sendEmailChangeFinal(
    to: string,
    finalUrl: string,
  ): Promise<boolean> {
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
      </head>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <h2 style="color: #18181b; margin: 0 0 24px 0; font-size: 24px;">Finalize Your Email Address Change</h2>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
              Please click the button below to make <strong>${to}</strong> your new login email for GlobalConnect.
            </p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="${finalUrl}" target="_blank" style="display: inline-block; background-color: #16a34a; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Finalize Change</a>
            </div>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 0;">
              This link expires in <strong>15 minutes</strong>.
            </p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 14px; margin: 0;">— The GlobalConnect Team</p>
          </div>
        </div>
      </body>
      </html>
    `;

    return this.sendEmail({
      to,
      subject: 'Finalize Your Email Address Change - GlobalConnect',
      html,
    });
  }

  // Organization Invitation Email
  async sendInvitationEmail(
    to: string,
    inviterName: string,
    organizationName: string,
    invitationUrl: string,
  ): Promise<boolean> {
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
      </head>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <h2 style="color: #18181b; margin: 0 0 24px 0; font-size: 24px;">You've Been Invited!</h2>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">Hi there,</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
              <strong>${inviterName}</strong> has invited you to join their organization <strong>${organizationName}</strong> on <strong>GlobalConnect</strong>.
            </p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
              Click the button below to accept your invitation and create your account:
            </p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="${invitationUrl}" target="_blank" style="display: inline-block; background-color: #16a34a; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Accept Invitation</a>
            </div>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 0 0 16px 0;">
              This invitation link will expire in <strong>7 days</strong> for your security.
            </p>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 0;">
              If you weren't expecting this invitation, you can safely ignore this email.
            </p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 14px; margin: 0;">— The GlobalConnect Team</p>
          </div>
        </div>
      </body>
      </html>
    `;

    return this.sendEmail({
      to,
      subject: `You're Invited to Join ${organizationName} on GlobalConnect`,
      html,
    });
  }

  // Organization Deletion Scheduled Email
  async sendOrgDeletionScheduledEmail(
    to: string,
    orgName: string,
    deletionDate: Date,
    restoreUrl: string,
  ): Promise<boolean> {
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
      </head>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <h2 style="color: #dc2626; margin: 0 0 24px 0; font-size: 24px;">Organization Scheduled for Deletion</h2>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
              This is a notification that the organization <strong>${orgName}</strong> is scheduled to be permanently deleted on <strong>${deletionDate.toLocaleDateString()}</strong>.
            </p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
              If this was a mistake, you can restore your organization by clicking the button below:
            </p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="${restoreUrl}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Restore My Organization</a>
            </div>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 0;">
              This restore link is valid until the deletion date.
            </p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 14px; margin: 0;">— The GlobalConnect Team</p>
          </div>
        </div>
      </body>
      </html>
    `;

    return this.sendEmail({
      to,
      subject: `Your Organization "${orgName}" is Scheduled for Deletion`,
      html,
    });
  }

  // Organization Permanently Deleted Email
  async sendOrgPermanentlyDeletedEmail(
    to: string,
    orgName: string,
  ): Promise<boolean> {
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
      </head>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f5;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <h2 style="color: #dc2626; margin: 0 0 24px 0; font-size: 24px;">Organization Permanently Deleted</h2>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
              This is a confirmation that the organization <strong>${orgName}</strong> has been permanently deleted from GlobalConnect.
            </p>
            <p style="color: #dc2626; font-size: 14px; line-height: 1.6; margin: 0 0 16px 0; font-weight: 600;">
              This action cannot be undone.
            </p>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 0;">
              If you have any questions or believe this was done in error, please contact our support team.
            </p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 14px; margin: 0;">— The GlobalConnect Team</p>
          </div>
        </div>
      </body>
      </html>
    `;

    return this.sendEmail({
      to,
      subject: `Your Organization "${orgName}" Has Been Permanently Deleted`,
      html,
    });
  }
}
