// api-gateway/src/index.ts

import {
  ApolloGateway,
  IntrospectAndCompose,
  RemoteGraphQLDataSource,
} from "@apollo/gateway";
import { ApolloServer } from "@apollo/server";
import "dotenv/config";

// --- NEW IMPORTS FOR EXPRESS ---
import express from "express";
import http from "http";
import cors from "cors";
import { json } from "body-parser";
import { expressMiddleware } from "@apollo/server/express4";
import { ApolloServerPluginDrainHttpServer } from "@apollo/server/plugin/drainHttpServer";
import { createProxyMiddleware } from "http-proxy-middleware";
import type { Options as HttpProxyMiddlewareOptions } from "http-proxy-middleware";
// -----------------------------

// We no longer need the JWT secret in the gateway
// if (!process.env.JWT_SECRET) {
//   throw new Error(
//     "FATAL_ERROR: JWT_SECRET environment variable is not defined."
//   );
// }

class AuthenticatedDataSource extends RemoteGraphQLDataSource {
  override willSendRequest({
    request,
    context,
  }: {
    request: any;
    context: any;
  }) {
    if (context.authorization) {
      request.http.headers.set("Authorization", context.authorization);
    }
  }
}

// This function will create and start our server
async function startServer() {
  const app = express();
  const httpServer = http.createServer(app);

  const gateway = new ApolloGateway({
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
    plugins: [ApolloServerPluginDrainHttpServer({ httpServer })],
  });

  await server.start();

  // --- ADD THE NEW PROXY MIDDLEWARE ---
  const eventServiceUrl = process.env.EVENT_LIFECYCLE_SERVICE_URL?.replace(
    "/graphql",
    ""
  );
  if (eventServiceUrl) {
    interface ProxyRequestHandlerOptions extends HttpProxyMiddlewareOptions {
      onProxyReq?: (
      proxyReq: http.ClientRequest,
      req: express.Request,
      res: express.Response
      ) => void;
    }

    app.use(
      "/api",
      cors<cors.CorsRequest>({
      origin: process.env.CLIENT_URL || "http://localhost:3000",
      credentials: true,
      }),
      createProxyMiddleware({
      target: eventServiceUrl,
      changeOrigin: true,
      onProxyReq: (
        proxyReq: http.ClientRequest,
        req: express.Request,
        res: express.Response
      ) => {
        // Forward the original authorization header
        if (req.headers.authorization) {
        proxyReq.setHeader("Authorization", req.headers.authorization);
        }
      },
      } as ProxyRequestHandlerOptions)
    );
    console.log(`📬 Proxying REST requests for /api to ${eventServiceUrl}`);
  } else {
    console.error(
      "EVENT_LIFECYCLE_SERVICE_URL is not defined. REST proxy will not be enabled."
    );
  }
  // ------------------------------------

  app.use(
    "/graphql",
    cors<cors.CorsRequest>({
      origin: process.env.CLIENT_URL || "http://localhost:3000",
      credentials: true,
    }),
    json(),
    expressMiddleware(server, {
      context: async ({ req }) => {
        // We just pass the authorization header through, without verifying it here.
        return { authorization: req.headers.authorization };
      },
    })
  );

  await new Promise<void>((resolve) =>
    httpServer.listen({ port: 4000 }, resolve)
  );
  console.log(`🚀 Gateway ready at: http://localhost:4000/graphql`);
}

startServer();
