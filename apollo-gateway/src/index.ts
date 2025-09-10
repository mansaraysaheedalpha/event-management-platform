// api-gateway/src/index.ts

import { ApolloGateway, IntrospectAndCompose, RemoteGraphQLDataSource } from "@apollo/gateway";
import { ApolloServer } from "@apollo/server";
import "dotenv/config";
import jwt from "jsonwebtoken";

// --- NEW IMPORTS FOR EXPRESS ---
import express from "express";
import http from "http";
import cors from "cors";
import { json } from "body-parser";
import {expressMiddleware} from "@apollo/server/express4"
import { ApolloServerPluginDrainHttpServer } from "@apollo/server/plugin/drainHttpServer";
// -----------------------------

if (!process.env.JWT_SECRET) {
  throw new Error(
    "FATAL_ERROR: JWT_SECRET environment variable is not defined."
  );
}

// Your UserContext and AuthenticatedDataSource classes remain the same
interface UserContext {
  userId: string;
  orgId: string;
  role: string;
  permissions: string[];
}

class AuthenticatedDataSource extends RemoteGraphQLDataSource {
  override async willSendRequest(options: any): Promise<void> {
    const { context, request } = options;
    if (context.user) {
      request.http?.headers.set("x-user-context", JSON.stringify(context.user));
    }
  }
}

// This function will create and start our server
async function startServer() {
  const app = express();
  const httpServer = http.createServer(app);

  const gateway = new ApolloGateway({
    // Your gateway config is unchanged
    supergraphSdl: new IntrospectAndCompose({
      subgraphs: [
        { name: "user-org", url: process.env.USER_ORG_SERVICE_URL },
        {
          name: "event-lifecycle",
          url: process.env.EVENT_LIFECYCLE_SERVICE_URL,
        },
        { name: "ai-oracle", url: process.env.AI_ORACLE_SERVICE_URL },
      ],
    }),
    buildService(service) {
      return new AuthenticatedDataSource({ url: service.url });
    },
  });

  const server = new ApolloServer({
    gateway,
    // This plugin helps gracefully shut down the server
    plugins: [ApolloServerPluginDrainHttpServer({ httpServer })],
  });

  await server.start();

  // Apply middleware to the Express app
  app.use(
    "/graphql",
    // THIS IS THE CORS FIX
    cors<cors.CorsRequest>({
      origin: "http://localhost:3000", // Allow requests from your frontend
      credentials: true,
    }),
    json(),
    // This connects Apollo Server to Express
    expressMiddleware(server, {
      context: async ({ req }) => {
        const token = req.headers.authorization?.split(" ")[1] || "";
        if (token) {
          try {
            const user = jwt.verify(
              token,
              process.env.JWT_SECRET as string
            ) as unknown as UserContext;
            return { user };
          } catch (err) {
            console.error("JWT verification error:", (err as Error).message);
          }
        }
        return {};
      },
    })
  );

  // Start listening
  await new Promise<void>((resolve) =>
    httpServer.listen({ port: 4000 }, resolve)
  );
  console.log(`🚀 Gateway ready at: http://localhost:4000/graphql`);
}

startServer();
