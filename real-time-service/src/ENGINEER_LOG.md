# Engineer's Log: Real-Time Service

This document serves as a log of the key errors, bugs, and architectural challenges encountered and resolved during the development of the Real-Time service. Each entry includes an explanation of the problem and the final, robust solution.

---
### 1. Asynchronous Code Bugs (`async`/`await` and Promises)

* **Error:** `Property 'id' does not exist on type 'Promise<...>'` and `Expected non-Promise value in a boolean conditional`.
* **Context:** These errors appeared frequently in service methods (e.g., `PollsService.submitVote`) after calling a Prisma database function.
* **Explanation:** The root cause was a missing `await` keyword. An `async` function (like `prisma.$transaction`) immediately returns a `Promise` object, not the final result. The code was incorrectly trying to access properties on the `Promise` object itself, rather than waiting for it to resolve to the actual data object.
* **Solution:** The `await` keyword was added before any `async` database or service call to ensure the function pauses execution until the promise resolves. This correctly assigns the final data to the variable, making all subsequent property access valid.

* **Error:** `@typescript-eslint/no-floating-promises` on `redis.publish()` and `this.subscriber.subscribe()`.
* **Context:** The linter correctly identified that we were calling `async` methods without `await`ing them or handling potential errors.
* **Explanation:** These "fire-and-forget" actions needed to be handled gracefully. We didn't want a failed analytics event to block a successful chat message, but we also couldn't ignore the promise completely.
* **Solution:** We created small, private `async` helper methods (e.g., `_publishAuditEvent`) that contained the `try/catch` and `await` logic. The main business logic then calls this helper with the `void` operator (e.g., `void this._publishAuditEvent(...)`). This explicitly tells the linter we are intentionally not waiting for the promise to complete, while ensuring any errors within it are still caught and logged.

---
### 2. TypeScript & Linter Errors

* **Error:** `@typescript-eslint/no-misused-promises` on `setInterval` and `setTimeout` callbacks.
* **Context:** This occurred in the `ReactionsGateway` when trying to run an `async` function on a recurring timer.
* **Explanation:** `setInterval` and `setTimeout` are old JavaScript APIs that expect a function returning `void`. Passing an `async` function (which returns a `Promise`) can lead to unhandled errors and overlapping executions if the async task takes longer than the interval.
* **Solution:** We replaced the `setInterval` pattern with a more robust, recursive `setTimeout` loop. An `async` function `runBroadcastCycle` was created. At the end of its execution (in the `finally` block), it schedules the *next* call to itself with `setTimeout`. This guarantees that one cycle completes before the next one begins and allows for robust `try/catch` error handling within the async function.

* **Error:** `Unsafe assignment of an 'any' value` and `Unsafe member access` on `response.data` and `JSON.parse()`.
* **Context:** This happened repeatedly when handling data from `axios` (`HttpService`) calls or after using `JSON.parse()`.
* **Explanation:** Both `axios` and `JSON.parse()` return a value of type `any` by default because they cannot know the shape of the data at compile time. Our strict linter correctly forbids using these `any` values without validation.
* **Solution:** We established a strict pattern:
    1.  Create a dedicated DTO or `interface` for the expected data shape.
    2.  For `HttpService` calls, we provide this as a generic: `httpService.get<MyDto>(...)`.
    3.  For `JSON.parse()`, we first cast the result to `unknown` and then use a custom **type guard** function (e.g., `isAnalyticsEventPayload(payload): payload is AnalyticsEventPayload`) to perform runtime validation before using the data.

---
### 3. Prisma Schema Errors

* **Error:** `P1012: The relation field ... is missing an opposite relation field...`
* **Context:** This occurred when adding the `Incident` model and relating it to `ChatSession`.
* **Explanation:** Prisma requires that all relations are defined on **both** participating models. We defined the `session` field on `Incident` but forgot to add the corresponding `incidents` field on `ChatSession`.
* **Solution:** We added the missing field (`incidents Incident[]`) to the `ChatSession` model to complete the two-way relationship.

* **Error:** `P1012: Embedded many-to-many relations are not supported on Postgres.`
* **Context:** This happened when first designing the `Conversation` and `UserReference` relationship.
* **Explanation:** The initial schema attempted to link the models using an array of IDs, a pattern valid for document databases like MongoDB but not for relational databases like PostgreSQL.
* **Solution:** We refactored the schema to use Prisma's standard **implicit many-to-many** relation. We removed the incorrect manual join table and simply defined the relation fields on both sides (`conversations Conversation[]` on the `UserReference` model and `participants UserReference[]` on the `Conversation` model), allowing Prisma to manage the join table automatically.

* **Error:** `P1012: Type 'JsonValue' is not assignable to type 'InputJsonValue'`.
* **Context:** This occurred in the `ChatService` when trying to write a complex Prisma object to a `Json` field in the `SyncLog` table using `createMany`.
* **Explanation:** The object returned from a `prisma.create()` call is a complex class instance, which is not a plain, serializable object that the `InputJsonValue` type expects for write operations.
* **Solution:** We converted the complex Prisma object into a pure, serializable data object before saving it to the log using `JSON.parse(JSON.stringify(createdMessage))`. This strips all class methods and metadata, providing a plain object that satisfies Prisma's input type.

---
### 4. NestJS Module & Dependency Errors

* **Error:** `Module '"@nestjs/passport"' has no exported member 'AuthGuard' or 'PassportModule'`.
* **Context:** This occurred when setting up the `SyncController` with an `AuthGuard`.
* **Explanation:** The error was twofold. First, the `SyncController` was incorrectly placed in the `providers` array of its module instead of the `controllers` array. Second, the `PassportModule` itself needs to be installed (`@nestjs/passport`, `passport`, `passport-jwt`) and imported into the module where its features are used.
* **Solution:** We corrected the `SystemModule` by moving `SyncController` to the `controllers: []` array and adding `PassportModule.register(...)` to the `imports: []` array. We also confirmed all necessary `passport`-related packages were installed, and reset the `node_modules` directory to ensure a clean environment.