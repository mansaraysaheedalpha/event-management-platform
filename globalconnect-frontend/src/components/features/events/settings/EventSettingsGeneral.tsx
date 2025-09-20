// src/components/features/events/settings/EventSettingsGeneral.tsx
"use client";

import { useApolloClient } from "@apollo/client";
import { useAuthStore } from "@/store/auth.store";
import { GetEventByIdQuery } from "@/gql/graphql";
import { useImageUpload } from "@/hooks/use-image-upload";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ImageUpload } from "@/components/ui/image-upload";

type EventDetails = NonNullable<GetEventByIdQuery["event"]>;

export function EventSettingsGeneral({ event }: { event: EventDetails }) {
  const orgId = useAuthStore((state) => state.orgId);
  const client = useApolloClient();
  const { isUploading, uploadImage } = useImageUpload(orgId!, event.id);

  const handleImageChange = async (file: File) => {
    const updatedEvent = await uploadImage(file);
    if (updatedEvent) {
      // This forces Apollo Client to refetch any queries that include this event
      client.refetchQueries({
        include: ["GetEventsByOrganization", "GetEventById"],
      });
    }
  };

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Event Banner Image</CardTitle>
          <CardDescription>
            This is the main image for your event. Recommended size: 1200x628px.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ImageUpload
            value={event.imageUrl}
            onChange={handleImageChange}
            isUploading={isUploading}
          />
        </CardContent>
      </Card>
      {/* We will add forms to edit name, description, etc., here later */}
    </div>
  );
}
