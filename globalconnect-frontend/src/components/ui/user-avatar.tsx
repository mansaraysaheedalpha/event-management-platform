"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface UserAvatarProps {
  firstName: string;
  lastName: string;
  imageUrl?: string | null;
}

export function UserAvatar({ firstName, lastName, imageUrl }: UserAvatarProps) {
  const initials = `${firstName?.[0] ?? ""}${
    lastName?.[0] ?? ""
  }`.toUpperCase();

  return (
    <Avatar>
      {imageUrl && (
        <AvatarImage src={imageUrl} alt={`${firstName} ${lastName}`} />
      )}
      <AvatarFallback>{initials}</AvatarFallback>
    </Avatar>
  );
}
