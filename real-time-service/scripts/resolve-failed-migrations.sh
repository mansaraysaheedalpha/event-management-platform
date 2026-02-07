#!/bin/bash
# Script to resolve failed migrations in production

# Mark specific failed migrations as rolled back
echo "Checking for failed migrations..."

# List of migrations to mark as rolled back
FAILED_MIGRATIONS=(
  "20260207174531_add_user_profile_relation"
)

for migration in "${FAILED_MIGRATIONS[@]}"; do
  echo "Attempting to resolve migration: $migration"
  npx prisma migrate resolve --rolled-back "$migration" || echo "Migration $migration not found or already resolved"
done

echo "Failed migrations resolution complete"
