// test/polls.e2e-spec.ts

import * as io from 'socket.io-client';
import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { AppModule } from './../src/app.module';
import { PrismaService } from '../src/prisma.service';

jest.setTimeout(30000); // Increased timeout globally

describe('Polls Feature (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let adminSocket: any;
  let attendeeSocket: any;
  let pollId: string;
  let optionId: string;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleRef.createNestApplication();
    await app.init();

    prisma = app.get(PrismaService);

    const socketOptions = {
      transports: ['websocket'],
      forceNew: true,
      reconnection: false,
    };

    // Adjust max listeners to avoid warnings
    process.setMaxListeners(30);

    adminSocket = io.connect('http://localhost:3001/polls', socketOptions);
    attendeeSocket = io.connect('http://localhost:3001/polls', socketOptions);

    await new Promise((resolve) => setTimeout(resolve, 3000)); // wait for connection
  });

  afterAll(async () => {
    if (pollId) {
      await prisma.poll.deleteMany({ where: { id: pollId } });
    }
    if (adminSocket?.connected) adminSocket.disconnect();
    if (attendeeSocket?.connected) attendeeSocket.disconnect();
    await app.close();
  });

  it('Admin should be able to create a poll', (done) => {
    const pollData = {
      question: 'Is this a test poll?',
      options: [{ text: 'Yes' }, { text: 'No' }],
    };

    adminSocket.emit('poll.create', pollData, (createdPoll) => {
      expect(createdPoll).toHaveProperty('id');
      expect(createdPoll.question).toBe(pollData.question);
      expect(createdPoll.options.length).toBe(2);

      pollId = createdPoll.id;
      optionId = createdPoll.options[0].id;

      done();
    });
  });

  it('Should broadcast the new poll to all clients', (done) => {
    attendeeSocket.once('poll.opened', (newPoll) => {
      expect(newPoll.id).toBe(pollId);
      expect(newPoll.question).toBe('Is this a test poll?');
      done();
    });

    // Trigger broadcast again
    adminSocket.emit('poll.create', {
      question: 'Is this a test poll?',
      options: [{ text: 'Yes' }, { text: 'No' }],
    });
  });

  it('Attendee should be able to vote on the poll', (done) => {
    const voteData = {
      pollId,
      optionId,
    };

    attendeeSocket.emit('poll.vote', voteData, (response) => {
      expect(response.message).toBe('Vote recorded');
      done();
    });
  });

  it('Should broadcast the updated poll results to all clients', (done) => {
    adminSocket.once('poll.results.updated', (updatedPoll) => {
      expect(updatedPoll.poll.id).toBe(pollId);
      expect(updatedPoll.poll.totalVotes).toBe(1);
      done();
    });

    // Trigger broadcast by casting a vote again
    attendeeSocket.emit('poll.vote', { pollId, optionId });
  });
});
