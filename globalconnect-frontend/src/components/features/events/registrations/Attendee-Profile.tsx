// src/components/features/events/registrations/AttendeeProfile.tsx
"use client";

import { useQuery } from "@apollo/client";
import { GET_USER_BY_ID_QUERY } from "@/graphql/user.graphql";
import { UserAvatar } from "@/components/ui/user-avatar";
import { Skeleton } from "@/components/ui/skeleton";

interface AttendeeProfileProps {
  userId: string;
}

export function AttendeeProfile({ userId }: AttendeeProfileProps) {
  const { data, loading, error } = useQuery(GET_USER_BY_ID_QUERY, {
    variables: { id: userId },
  });

  if (loading) {
    return (
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-40" />
        </div>
      </div>
    );
  }

  if (error || !data?.user) {
    return (
      <div className="flex items-center gap-3">
        <UserAvatar firstName="Error" lastName="!" />
        <div className="flex flex-col">
          <span className="font-medium text-destructive">User not found</span>
          <span className="text-xs text-muted-foreground">ID: {userId}</span>
        </div>
      </div>
    );
  }

  const { user } = data;

  // THE FIX: More robust check for a valid name.
  // Handles null, undefined, empty strings, and the literal string "None".
  const hasFirstName = user.first_name && user.first_name !== "None";
  const hasLastName = user.last_name && user.last_name !== "None";
  const hasFullName = hasFirstName && hasLastName;

  const displayName = hasFullName
    ? `${user.first_name} ${user.last_name}`
    : user.email;

  const email = user.email;

  return (
    <div className="flex items-center gap-3">
      <UserAvatar
        firstName={user.first_name || user.email}
        lastName={user.last_name || ""}
      />
      <div className="flex flex-col">
        <span className="font-medium">{displayName}</span>
        <span className="text-xs text-muted-foreground">{email}</span>
      </div>
    </div>
  );
}
