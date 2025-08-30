import { ApolloGateway, RemoteGraphQLDataSource } from '@apollo/gateway';
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import 'dotenv/config';
import jwt from 'jsonwebtoken';
import { expressjwt as expressJwt } from 'express-jwt';


// Define the user context that will be passed down to services
interface UserContext {
  userId: string;
  orgId: string;
  role: string;
  permissions: string[];
}

// Custom data source to forward the user context
class AuthenticatedDataSource extends RemoteGraphQLDataSource {
  willSendRequest({ request, context }) {
    if (context.user) {
      const userContext = JSON.stringify(context.user);
      request.http.headers.set('x-user-context', userContext);
    }
  }
}

const gateway = new ApolloGateway({
  serviceList: [
    // These will be uncommented as we federate each service
    // { name: 'user-org', url: process.env.USER_ORG_SERVICE_URL },
    // { name: 'event-lifecycle', url: process.env.EVENT_LIFECYCLE_SERVICE_URL },
    // { name: 'ai-oracle', url: process.env.AI_ORACLE_SERVICE_URL },
    // { name: 'real-time', url: process.env.REAL_TIME_SERVICE_URL },
  ],
  buildService(service) {
    return new AuthenticatedDataSource({ url: service.url });
  },
});

const server = new ApolloServer({
  gateway,
});

async function startServer() {
  const { url } = await startStandaloneServer(server, {
    listen: { port: 4000 },
    context: async ({ req }) => {
      const token = req.headers.authorization?.split(' ')[1] || '';
      if (token) {
        try {
          const user = jwt.verify(token, process.env.JWT_SECRET) as UserContext;
          return { user };
        } catch (err) {
          // In case of invalid token, context will not have user
          console.error('JWT verification error:', err.message);
        }
      }
      return {};
    },
  });
  console.log(`🚀 Gateway ready at: ${url}`);
}

startServer();
