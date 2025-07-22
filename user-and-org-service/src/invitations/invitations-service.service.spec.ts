import { Test, TestingModule } from '@nestjs/testing';
import { InvitationsServiceService } from './invitations.service';

describe('InvitationsServiceService', () => {
  let service: InvitationsServiceService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [InvitationsServiceService],
    }).compile();

    service = module.get<InvitationsServiceService>(InvitationsServiceService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });
});
