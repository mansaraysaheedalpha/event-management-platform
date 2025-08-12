import { Test, TestingModule } from '@nestjs/testing';
import { StreamingGateway } from './streaming.gateway';
import { SubtitleChunkDto } from './dto/subtitle-chunk.dto';

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('StreamingGateway', () => {
  let gateway: StreamingGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [StreamingGateway],
    }).compile();

    gateway = module.get<StreamingGateway>(StreamingGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  it('should broadcast a subtitle chunk to the correct session room', () => {
    const payload: SubtitleChunkDto = {
      sessionId: 'session-456',
      text: 'This is a test',
      language: 'en',
      timestamp: new Date().toISOString(),
      duration: 1500,
    };

    gateway.broadcastSubtitleChunk(payload);

    expect(mockIoServer.to).toHaveBeenCalledWith('session:session-456');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'subtitle.stream.chunk',
      payload,
    );
  });
});
