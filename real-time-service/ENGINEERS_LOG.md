# Real-Time Service: Engineering Log & Debugging History

This document tracks all major errors encountered during the setup of the testing suite and CI/CD pipeline for the `real-time-service`.

---
### Error 1: E2E Test Failure - `secretOrPrivateKey must have a value`

* **Exact Error Message:** `secretOrPrivateKey must have a value`
* **What it Means:** The `JwtService` inside the E2E test environment did not have a secret key to sign tokens with, because the test process was not loading the `.env` file correctly.
* **Exact Solution:** We created a dedicated `test/setup-e2e.ts` file and added it to the `setupFiles` array in `jest-e2e.json`. This script uses `dotenv` to explicitly load the `.env` file before any tests run. We also updated the `test:e2e` script in `package.json` to use `cross-env` to reliably set `NODE_ENV=test`.
* **Resolution Attempts:** 5

---
### Error 2: E2E Test Failure - `ECONNREFUSED` (Connection Refused)

* **Exact Error Message:** `websocket error` with underlying `Error: connect ECONNREFUSED`
* **What it Means:** The test client could not establish a WebSocket connection to the NestJS server started by the test runner.
* **Exact Solution:** We corrected the `io()` connection call in `test/app.e2e-spec.ts`. The namespace was moved from the `path` option to the main URL (e.g., `http://localhost:${port}/events`), and the `path` was set to the correct Socket.IO default (`/socket.io/`).
* **Resolution Attempts:** 1

---
### Error 3: CI/CD & E2E Test Hang (`Jest did not exit`)

* **Symptom:** All E2E tests would pass, but the Jest process would not exit cleanly, causing the CI pipeline to time out.
* **What it Means:** A background process, most likely the Prisma database connection, was not being closed properly after the tests finished.
* **Exact Solution:** We implemented the `OnModuleDestroy` lifecycle hook in the `PrismaService` (`prisma.service.ts`) and added the `async onModuleDestroy() { await this.$disconnect(); }` method. This ensures NestJS automatically closes the database connection when the application shuts down.
* **Resolution Attempts:** 3

---
### Error 4: E2E Test Failure - `NoBrokersAvailable` (Kafka)

* **Exact Error Message:** `Exceeded timeout of 5000 ms for a hook`, with logs showing `NoBrokersAvailable`
* **What it Means:** The application could not start up during the E2E test because it was stuck trying to connect to a Kafka server that wasn't running.
* **Exact Solution:** We updated the local E2E testing workflow to include starting all necessary Docker dependencies with the command `docker-compose up -d db-test redis zookeeper kafka`.
* **Resolution Attempts:** 2

---
### Error 5: CI/CD Failure - `pnpm: command not found` / `NO_LOCKFILE`

* **Exact Error Message:** `ERR_PNPM_NO_LOCKFILE Cannot install with "frozen-lockfile" because pnpm-lock.yaml is absent`
* **What it Means:** The CI workflow was trying to run `pnpm install` in the wrong directory within the monorepo, where no `pnpm-lock.yaml` file existed.
* **Exact Solution:** We refactored the `.github/workflows/ci.yml` file to be monorepo-aware. We added a `defaults.run.working-directory: ./real-time-service` key to ensure all commands run from inside the correct service folder.
* **Resolution Attempts:** 4