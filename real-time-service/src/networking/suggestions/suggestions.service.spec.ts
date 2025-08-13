import { Test, TestingModule } from '@nestjs/testing';
import { SuggestionsService } from './suggestions.service';
import { SuggestionsGateway } from './suggestions.gateway';

const mockGateway = { sendSuggestion: jest.fn() };

describe('SuggestionsService', () => {
  let service: SuggestionsService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        SuggestionsService,
        { provide: SuggestionsGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<SuggestionsService>(SuggestionsService);
    jest.clearAllMocks();
  });

  it('should route an AI suggestion to the gateway', () => {
    const payload = {
      type: 'CONNECTION_SUGGESTION' as const,
      targetUserId: 'user-1',
    };
    service.handleAiSuggestion(payload);
    expect(mockGateway.sendSuggestion).toHaveBeenCalledWith(payload);
  });
});
