import { Test, TestingModule } from '@nestjs/testing';
import { SuggestionsGateway, AiSuggestionPayload } from './suggestions.gateway';

const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('SuggestionsGateway', () => {
  let gateway: SuggestionsGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [SuggestionsGateway],
    }).compile();
    gateway = module.get<SuggestionsGateway>(SuggestionsGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  it('should emit a "suggestion.connection" event for a CONNECTION_SUGGESTION', () => {
    const payload: AiSuggestionPayload = {
      type: 'CONNECTION_SUGGESTION',
      targetUserId: 'user-1',
    };
    gateway.sendSuggestion(payload);
    expect(mockIoServer.to).toHaveBeenCalledWith('user:user-1');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'suggestion.connection',
      payload,
    );
  });

  it('should emit a "suggestion.circle" event for a CIRCLE_SUGGESTION', () => {
    const payload: AiSuggestionPayload = {
      type: 'CIRCLE_SUGGESTION',
      targetUserId: 'user-1',
    };
    gateway.sendSuggestion(payload);
    expect(mockIoServer.to).toHaveBeenCalledWith('user:user-1');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'suggestion.circle',
      payload,
    );
  });
});
