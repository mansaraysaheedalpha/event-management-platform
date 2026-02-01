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

// Helper function to wait
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// Build subgraphs list - only include deployed services
function getSubgraphs() {
  const subgraphs: { name: string; url: string }[] = [];

  if (process.env.USER_ORG_SERVICE_URL) {
    subgraphs.push({ name: "user-org", url: process.env.USER_ORG_SERVICE_URL });
  }
  if (process.env.EVENT_LIFECYCLE_SERVICE_URL) {
    subgraphs.push({ name: "event-lifecycle", url: process.env.EVENT_LIFECYCLE_SERVICE_URL });
  }
  // AI Oracle is disabled for now - uncomment when deployed
  // if (process.env.AI_ORACLE_SERVICE_URL) {
  //   subgraphs.push({ name: "ai-oracle", url: process.env.AI_ORACLE_SERVICE_URL });
  // }

  return subgraphs;
}

// Global state for gateway status
let isGatewayReady = false;

// This function will create and start our server with retry logic
async function startServer(): Promise<void> {
  const MAX_RETRIES = 10;
  const RETRY_DELAY_MS = 15000; // 15 seconds between retries

  const subgraphs = getSubgraphs();

  if (subgraphs.length === 0) {
    console.error("No subgraph URLs configured. Please set environment variables.");
    process.exit(1);
  }

  // Create Express app and HTTP server FIRST (outside retry logic)
  const app = express();
  const httpServer = http.createServer(app);

  // Configure CORS - allow multiple client URLs
  // CLIENT_URL can be comma-separated: "https://example.com,https://www.example.com"
  // Supports wildcards: "https://*.vercel.app"
  const allowedOrigins = (process.env.CLIENT_URL || "http://localhost:3000")
    .split(",")
    .map((origin) => origin.trim());

  // Helper to check if origin matches allowed patterns (supports wildcards)
  const isOriginAllowed = (origin: string): boolean => {
    return allowedOrigins.some((pattern) => {
      // Exact match
      if (pattern === origin) return true;

      // Wildcard match: convert pattern to regex
      if (pattern.includes("*")) {
        const regexPattern = pattern
          .replace(/\./g, "\\.")  // Escape dots
          .replace(/\*/g, ".*");  // Replace * with .*
        const regex = new RegExp(`^${regexPattern}$`);
        return regex.test(origin);
      }

      return false;
    });
  };

  const corsOptions: cors.CorsOptions = {
    origin: (origin, callback) => {
      // Allow requests with no origin (like mobile apps or curl)
      if (!origin) {
        callback(null, true);
        return;
      }
      // Check if the origin matches allowed patterns
      if (isOriginAllowed(origin)) {
        callback(null, origin); // Return only the matching origin
      } else {
        console.warn(`CORS blocked origin: ${origin}`);
        callback(new Error("Not allowed by CORS"));
      }
    },
    credentials: true,
  };

  // Apply CORS globally to handle preflight requests
  app.use(cors(corsOptions));

  // Health check endpoint - available immediately
  app.get("/health", (req, res) => {
    res.json({
      status: "ok",
      service: "apollo-gateway",
      gatewayReady: isGatewayReady,
      timestamp: new Date().toISOString()
    });
  });

  // --- REST PROXY MIDDLEWARE ---
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
    console.log(`Proxying REST requests for /api to ${eventServiceUrl}`);
  }
  // ------------------------------------

  // Start the HTTP server immediately so it can respond to health checks and CORS
  const port = process.env.PORT || 4000;
  await new Promise<void>((resolve) =>
    httpServer.listen({ port: Number(port) }, resolve)
  );
  console.log(`HTTP server started on port ${port}, waiting for gateway...`);

  // Now try to connect to subgraphs with retry logic
  for (let retryCount = 0; retryCount < MAX_RETRIES; retryCount++) {
    console.log(`[Attempt ${retryCount + 1}/${MAX_RETRIES}] Connecting to subgraphs:`, subgraphs.map(s => s.name).join(", "));

    try {
      const gateway = new ApolloGateway({
        supergraphSdl: new IntrospectAndCompose({
          subgraphs,
          // Poll for schema updates every 30 seconds
          pollIntervalInMs: 30000,
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

      // Add GraphQL endpoint
      app.use(
        "/graphql",
        json(),
        expressMiddleware(server, {
          context: async ({ req }) => {
            return { authorization: req.headers.authorization };
          },
        })
      );

      isGatewayReady = true;
      console.log(`Gateway ready at: http://localhost:${port}/graphql`);
      return; // Success, exit the function

    } catch (error) {
      console.error(`Failed to start gateway:`, error instanceof Error ? error.message : error);

      if (retryCount < MAX_RETRIES - 1) {
        console.log(`Retrying in ${RETRY_DELAY_MS / 1000} seconds...`);
        await sleep(RETRY_DELAY_MS);
      } else {
        console.error(`Max retries (${MAX_RETRIES}) reached. Gateway failed to start.`);
        // Don't exit - keep server running for health checks, but gateway won't work
        app.use("/graphql", (req, res) => {
          res.status(503).json({ error: "Gateway unavailable - subgraphs not reachable" });
        });
      }
    }
  }
}

startServer();
