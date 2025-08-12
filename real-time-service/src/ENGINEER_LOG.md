# Engineer's Log: Real-Time Service

This document serves as a log of the key errors, bugs, and architectural challenges encountered and resolved during the development of the Real-Time service. Each entry includes an explanation of the problem and the final, robust solution.

---
### 1. Asynchronous Code Bugs (`async`/`await` and Promises)

* **Error**: `Property 'id' does not exist on type 'Promise<...>'` and `Expected non-Promise value in a boolean conditional`.
* **Context**: These errors appeared frequently in service methods (e.g., `PollsService.submitVote`) after calling a Prisma database function.
* **Explanation**: The root cause was a missing `await` keyword. An `async` function (like `prisma.$transaction`) immediately returns a `Promise` object, not the final result. The code was incorrectly trying to access properties on the `Promise` object itself, rather than waiting for it to resolve to the actual data object.
* **Solution**: The `await` keyword was added before any `async` database or service call to ensure the function pauses execution until the promise resolves. This correctly assigns the final data to the variable, making all subsequent property access valid.

* **Error**: `@typescript-eslint/no-floating-promises` on `redis.publish()` and `this.subscriber.subscribe()`.
* **Context**: The linter correctly identified that we were calling `async` methods without `await`ing them or handling potential errors.
* **Explanation**: These "fire-and-forget" actions needed to be handled gracefully. We didn't want a failed analytics event to block a successful chat message, but we also couldn't ignore the promise completely.
* **Solution**: We created small, private `async` helper methods (e.g., `_publishAuditEvent`) that contained the `try/catch` and `await` logic. The main business logic then calls this helper with the `void` operator (e.g., `void this._publishAuditEvent(...)`). This explicitly tells the linter we are intentionally not waiting for the promise to complete, while ensuring any errors within it are still caught and logged.

---
### 2. TypeScript & Linter Errors

* **Error**: `@typescript-eslint/no-misused-promises` on `setInterval` and `setTimeout` callbacks.
* **Context**: This occurred in the `ReactionsGateway` when trying to run an `async` function on a recurring timer.
* **Explanation**: `setInterval` and `setTimeout` are old JavaScript APIs that expect a function returning `void`. Passing an `async` function (which returns a `Promise`) can lead to unhandled errors and overlapping executions if the async task takes longer than the interval.
* **Solution**: We replaced the `setInterval` pattern with a more robust, recursive `setTimeout` loop. An `async` function `runBroadcastCycle` was created. At the end of its execution (in the `finally` block), it schedules the *next* call to itself with `setTimeout`. This guarantees that one cycle completes before the next one begins and allows for robust `try/catch` error handling within the async function.

* **Error**: `Unsafe assignment of an 'any' value` and `Unsafe member access` on `response.data` and `JSON.parse()`.
* **Context**: This happened repeatedly when handling data from `axios` (`HttpService`) calls or after using `JSON.parse()`.
* **Explanation**: Both `axios` and `JSON.parse()` return a value of type `any` by default because they cannot know the shape of the data at compile time. Our strict linter correctly forbids using these `any` values without validation.
* **Solution**: We established a strict pattern:
    1.  Create a dedicated DTO or `interface` for the expected data shape.
    2.  For `HttpService` calls, we provide this as a generic: `httpService.get<MyDto>(...)`.
    3.  For `JSON.parse()`, we first cast the result to `unknown` and then use a custom **type guard** function (e.g., `isAnalyticsEventPayload(payload): payload is AnalyticsEventPayload`) to perform runtime validation before using the data.

---
### 3. Prisma Schema Errors

* **Error**: `P1012: The relation field ... is missing an opposite relation field...`
* **Context**: This occurred when adding the `Incident` model and relating it to `ChatSession`.
* **Explanation**: Prisma requires that all relations are defined on **both** participating models. We defined the `session` field on `Incident` but forgot to add the corresponding `incidents` field on `ChatSession`.
* **Solution**: We added the missing field (`incidents Incident[]`) to the `ChatSession` model to complete the two-way relationship.

* **Error**: `P1012: Embedded many-to-many relations are not supported on Postgres.`
* **Context**: This happened when first designing the `Conversation` and `UserReference` relationship.
* **Explanation**: The initial schema attempted to link the models using an array of IDs, a pattern valid for document databases like MongoDB but not for relational databases like PostgreSQL.
* **Solution**: We refactored the schema to use Prisma's standard **implicit many-to-many** relation. We removed the incorrect manual join table and simply defined the relation fields on both sides (`conversations Conversation[]` on the `UserReference` model and `participants UserReference[]` on the `Conversation` model), allowing Prisma to manage the join table automatically.

* **Error**: `P1012: Type 'JsonValue' is not assignable to type 'InputJsonValue'`.
* **Context**: This occurred in the `ChatService` when trying to write a complex Prisma object to a `Json` field in the `SyncLog` table using `createMany`.
* **Explanation**: The object returned from a `prisma.create()` call is a complex class instance, which is not a plain, serializable object that the `InputJsonValue` type expects for write operations.
* **Solution**: We manually constructed a new, plain JavaScript object containing only the pure data we needed. This plain object perfectly matched the expected type and was fully type-safe, resolving the issue without needing unsafe type casting.

---
### 4. NestJS Startup & Dependency Injection Errors

* **Error**: `UndefinedDependencyException: Nest can't resolve dependencies of the [Service]... Please make sure that the argument [Dependency] is available in the [Module] context.`
* **Context**: This error occurred multiple times with different services (`SubscriberService`, `AgendaService`, `ContentService`) after we performed a major architectural refactor.
* **Explanation**: This is a classic NestJS error that happens when its dependency injection system cannot find a provider that a class needs. We discovered several root causes:
    1.  **Circular File Imports**: Our `shared.module.ts` was importing a service (`SubscriberService`), which was simultaneously importing a token from `shared.module.ts`. This created an infinite loop that prevented either file from loading correctly.
    2.  **Missing Module Imports**: A feature module (like `ContentModule`) needed a provider (like `REDIS_CLIENT`) from a shared module, but it was not importing that shared module directly, leading to a broken dependency chain.
    3.  **Incorrect Architectural Pattern**: A major refactor where we moved all gateway providers to the `AppModule` was an incorrect pattern. It broke the encapsulation of our feature modules, making it impossible for services (like `AgendaService`) to find their own gateways, which were now being created in a different context.
* **Solution**: We implemented a definitive, multi-step solution that represents a world-class NestJS architecture:
    1.  **Broke the Circular Import**: We created a `src/shared/redis.constants.ts` file to hold our shared injection tokens. This file has no other dependencies, which completely breaks the circular import loop.
    2.  **Reverted the Centralized Gateway Pattern**: We returned to the standard and most robust NestJS pattern: **each feature module is self-contained**. `ChatModule` provides `ChatService` AND `ChatGateway`. `PollsModule` provides `PollsService` AND `PollsGateway`, and so on. This makes the dependency graph clean and predictable.
    3.  **Used `forwardRef()` for Co-dependencies**: For modules where the Service and Gateway depended on each other (a true circular dependency), we used NestJS's built-in `forwardRef()` function to lazily resolve one of the dependencies, breaking the loop at the injection site.

---
### 5. WebSocket & Node.js Environment Warnings

* **Warning**: `(node:...) MaxListenersExceededWarning: Possible EventEmitter memory leak detected. 11 connection listeners added to [Namespace]. MaxListeners is 10.`
* **Context**: This warning appeared after we had created many WebSocket gateways for our features.
* **Explanation**: The warning is not just about the `handleConnection` method. In NestJS, every single class decorated with `@WebSocketGateway()` adds a listener to the underlying Socket.IO server's `connection` event. With more than 10 gateways, we exceeded Node.js's default safety limit.
* **Solution**: We implemented a simple, clean, and officially supported solution. In our single `AppGateway` (the "front door" for all connections), we implemented the `OnGatewayInit` lifecycle hook. Inside the `afterInit` method, we get a direct reference to the main `Server` instance and increase its listener limit to a safe number (`server.setMaxListeners(30)`), permanently resolving the warning without complex architectural changes.

---
### 6. Git Workflow & Environment Errors

* **Error**: `The splatting operator '@' cannot be used...` when running `pnpm install @socket.io/redis-adapter`.
* **Context**: This was an environment-specific error when trying to install a scoped npm package.
* **Explanation**: The `@` symbol is a reserved character in PowerShell used for a feature called "splatting." When the command was run, PowerShell misinterpreted `@socket.io` and threw a syntax error.
* **Solution**: We wrapped the package name in quotes (`pnpm install "@socket.io/redis-adapter"`). This tells PowerShell to treat the entire string as a single, literal argument, ignoring any special characters within it.

* **Error**: Running `git rm --cached -r .` resulted in all project files being staged for deletion.
* **Context**: This was an attempt to fix harmless line-ending warnings that resulted in a dangerous command being run.
* **Explanation**: The `git rm --cached -r .` command tells Git to "stop tracking every file in this project." While it doesn't delete the local files, it puts the repository into a state where the next commit would wipe out the entire project history.
* **Solution**: Because the change was only staged and not yet committed, the definitive fix was to run `git reset`. This command unstages all changes, effectively undoing the `rm` operation and restoring Git's tracking of all project files, completely reverting the mistake.