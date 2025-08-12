import { Test, TestingModule } from '@nestjs/testing';
import { ValidationService } from './validation.service';
import { HttpService } from '@nestjs/axios';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';
import { ConflictException } from '@nestjs/common';
import { of } from 'rxjs';
import { AxiosResponse } from 'axios';
import { ValidationResultDto } from './dto/validation-result.dto';
import { ValidateTicketDto, ValidationType } from './dto/validate-ticket.dto';

const mockHttp = { post: jest.fn() };
const mockIdempotency = { checkAndSet: jest.fn() };
const mockPublisher = { publish: jest.fn() };

describe('ValidationService', () => {
  let service: ValidationService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        ValidationService,
        { provide: HttpService, useValue: mockHttp },
        { provide: IdempotencyService, useValue: mockIdempotency },
        { provide: PublisherService, useValue: mockPublisher },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    service = module.get<ValidationService>(ValidationService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  const eventId = 'event-1';
  const validateDto: ValidateTicketDto = {
    ticketCode: 'TICKET123',
    validationType: ValidationType.QR_CODE,
    idempotencyKey: 'key-1',
  };

  it('should call the external event service and publish an analytics event on valid ticket', async () => {
    mockIdempotency.checkAndSet.mockResolvedValue(true);

    const validationResult: ValidationResultDto = {
      isValid: true,
      ticketCode: 'TICKET123',
      validatedAt: new Date(),
      user: { id: 'user-1', name: 'Test User' },
    };
    const apiResponse: AxiosResponse = {
      data: validationResult,
      status: 200,
    } as any;
    mockHttp.post.mockReturnValue(of(apiResponse));

    const result = await service.validateTicket(eventId, validateDto);

    expect(mockHttp.post).toHaveBeenCalled();
    expect(mockPublisher.publish).toHaveBeenCalledWith(
      'platform.analytics.check-in.v1',
      expect.objectContaining({ type: 'CHECK_IN_PROCESSED' }),
    );
    expect(result.isValid).toBe(true);
  });

  it('should NOT publish an analytics event if ticket is invalid', async () => {
    mockIdempotency.checkAndSet.mockResolvedValue(true);
    const validationResult: ValidationResultDto = {
      isValid: false,
      ticketCode: 'TICKET123',
      validatedAt: new Date(),
    };
    const apiResponse: AxiosResponse = {
      data: validationResult,
      status: 200,
    } as any;
    mockHttp.post.mockReturnValue(of(apiResponse));

    await service.validateTicket(eventId, validateDto);

    expect(mockPublisher.publish).not.toHaveBeenCalled();
  });

  it('should throw ConflictException on duplicate request', async () => {
    mockIdempotency.checkAndSet.mockResolvedValue(false);
    await expect(service.validateTicket(eventId, validateDto)).rejects.toThrow(
      ConflictException,
    );
  });
});
