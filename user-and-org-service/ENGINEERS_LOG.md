# The Engineer's Logbook: Problems & Solutions

This document tracks the real-world environment, configuration, and code issues encountered during the development of the Multi-Tenant SaaS a project, and the solutions implemented.

---

### **Log Entry #1: Docker Connection Failure**

- **The Error:** `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.`
- **The Simple Meaning:** The command-line tool (the "steering wheel") could not communicate with the Docker Desktop application (the "engine").
- **The Solution:** The Docker Desktop application was not running or was in a faulty state. The fix was to ensure Docker Desktop was launched and fully running (showing a green "Running" status) before executing `docker-compose` commands. A full computer reboot is often the most effective first step.

---

### **Log Entry #2: Docker Compose Syntax Error**

- **The Error:** `invalid containerPort: 5432`
- **The Simple Meaning:** The version of Docker Compose being used was very strict and did not understand the syntax in the `ports` section of the `docker-compose.yml` file.
- **The Solution:** The `docker-compose.yml` file was corrected by removing the obsolete `version` tag and ensuring the `ports` mapping ` - "5432:5432"` was perfectly formatted.

---

### **Log Entry #3: Prisma Connection String Error (P1013)**

- **The Error:** `P1013: The provided database string is invalid. empty host in database URL.`
- **The Simple Meaning:** Prisma could not understand the database address because a special character (`@`) inside the password was confusing it. The `@` symbol is a reserved character that separates the credentials from the host address.
- **The Solution:** The password was changed in both the `docker-compose.yml` and `.env` files to a simpler password containing only letters and numbers, removing the special character conflict.

---

### **Log Entry #4: Prisma Authentication Error (P1000)**

- **The Error:** `P1000: Authentication failed against database server...`
- **The Simple Meaning:** Prisma successfully connected to the database server, but the username and password it provided were rejected.
- **The Solution:** This was caused by Docker's **persistent volume**. The database was first created with an old password, and that data was saved. Even after updating the configuration, the new container was using the old data. The fix was to completely destroy the old state by running `docker-compose down` followed by `docker volume rm [volume_name]` to delete the persistent data, and then running `docker-compose up -d` to create a truly fresh database instance with the new credentials.

---

### **Log Entry #5: Prisma Schema Attribute Error**

- **The Error:** `Attribute not known: "@relations".`
- **The Simple Meaning:** A typo was made in the `schema.prisma` file.
- **The Solution:** The attribute was corrected from the plural `@relations` to the correct singular form, `@relation`.

---

##
- **The Error:** `The operand of a 'delete' operator must be optional`
- **The Simple Meaning: **

### **Log Entry #6: TypeScript Function Call Typo**

* **The Error:** `TS2554: Expected 0 arguments, but got 1.` on the line `Math.random.toString(36)`.
* **The Simple Meaning:** The code was trying to call the `.toString()` method on the *recipe* for a random number (`Math.random`), instead of on the *actual random number* that the recipe produces.
* **The Solution:** The function must be called first by adding parentheses `()`. The corrected code is `Math.random().toString(36)`. This was a typo in the mentor's original code.

---

### **Log Entry #7: TypeScript `delete` Operator Error**

* **The Error:** `The operand of a 'delete' operator must be optional.`
* **The Simple Meaning:** TypeScript protects you from breaking an object's "contract" or shape. It prevents you from deleting a property that is defined as being required, as this could cause errors in other parts of the code that expect that property to exist.
* **The Solution:** Instead of mutating (changing) the original object with `delete`, the professional pattern is to create a *new* object that has the desired shape. We use object destructuring with the rest syntax to accomplish this: `const { password, ...objectToReturn } = originalObject;`. This creates a clean copy without the sensitive field.

---

### **Log Entry #8: `bcrypt` Runtime Error**

* **The Error:** `TypeError: Cannot read properties of undefined (reading 'hash')`
* **The Simple Meaning:** The code was trying to call the `.hash()` method on an object that was `undefined`. This was likely due to a subtle issue with the way the `bcryptjs` library was being imported and used in a single line.
* **The Solution:** The engineer (you, Saheed) independently debugged this by refactoring the logic into a more robust, two-step process that is guaranteed to work: 1. Generate the salt first with `const salt = await bcrypt.genSalt(10);`. 2. Use that salt to hash the password with `const hashedPassword = await bcrypt.hash(password, salt);`.

---

### **Log Entry #9: Prisma Migration on Non-Empty Table**

* **The Error:** `P1012: We found changes that cannot be executed: ... Added the required column ... to the User table without a default value. There are 1 rows in this table...`
* **The Simple Meaning:** The database is protecting itself. It cannot add a new, **required** column to a table that already has data because it doesn't know what value to put in that new column for the existing rows.
* **The Solution:** The change must be made non-breaking. In the `prisma/schema.prisma` file, the new column must be made **optional** by adding a `?` to its type definition (e.g., `hashedRefreshToken String?`). This tells the database that it's okay to leave the new column empty (`NULL`) for all existing rows.

---

# User & Org Service: Engineering Log & Debugging History

This document tracks all major errors encountered during the setup of the testing suite and CI/CD pipeline for the `user-and-org-service`.

---
### Error 1: Multiple Jest Configurations Found

* **Exact Error Message:** `Multiple configurations found: ... jest.config.js ... `jest` key in ... package.json`
* **What it Means:** Jest found configuration instructions in two separate places (`jest.config.js` and `package.json`) and stopped because it didn't know which one to use.
* **Exact Solution:** We made `jest.config.js` the single source of truth by deleting the entire `"jest": { ... }` block from the `package.json` file.
* **Resolution Attempts:** 1

---
### Error 2: Widespread Unit Test Failures (`Cannot find module`)

* **Exact Error Message:** `Cannot find module 'src/prisma.service' from 'audit/audit.service.ts'` (and many similar errors).
* **What it Means:** The tests were failing because they used absolute import paths (e.g., `src/prisma.service`), but the Jest test runner didn't know where the `src/` folder was located.
* **Exact Solution:** We created a `jest.config.js` file and added a `moduleNameMapper` configuration that told Jest how to resolve the `src/` path alias correctly.
* **Resolution Attempts:** 1

---
### Error 3: E2E Test Failure - Database Does Not Exist

* **Exact Error Message:** `PrismaClientInitializationError: Database 'user_org_db' does not exist`
* **What it Means:** The E2E test was connecting to the test PostgreSQL server, but was trying to use the *development* database name (`user_org_db`) instead of the *test* database name (`user_org_db_test`).
* **Root Cause:** The `NODE_ENV=test` variable was not being correctly prioritized, causing the application to load the default `.env` file instead of a test-specific configuration.
* **Exact Solution:** We created a dedicated `.env.test` file and updated the `ConfigModule` in `app.module.ts` to explicitly load this file when `process.env.NODE_ENV === 'test'`. This forced the test to use the correct database connection string.
* **Resolution Attempts:** 3

---
### Error 4: E2E Test Failure - System Role Not Found

* **Exact Error Message:** `Error: System role OWNER not found. Please seed the database.`
* **What it Means:** The user registration endpoint failed with a 500 Internal Server Error because the logic requires a special "OWNER" role to exist in the database, but the clean test database was empty.
* **Exact Solution:** We "seeded" the test database by adding a command to the `beforeAll` block in the `test/app.e2e-spec.ts` file to create the required `OWNER` role (`await prisma.role.create(...)`) before any tests were run.
* **Resolution Attempts:** 1

---
### Error 5: E2E Test Hang (`Jest did not exit`)

* **Symptom:** All E2E tests would pass, but the Jest process would hang and not exit, causing the local test run and the CI pipeline to fail.
* **What it Means:** A background process, like a database or mailer connection, was not being closed properly after the tests finished.
* **Exact Solution:** After several attempts to close individual connections, the definitive solution was to modify the `test:e2e` script in `package.json` to include the `--forceExit` and `--runInBand` flags. This is a pragmatic and robust solution that forces Jest to shut down cleanly after the tests pass.
* **Resolution Attempts:** 4