// src/components/features/events/EventTabs.tsx
"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GetEventByIdQuery } from "@/gql/graphql";
import { EventOverview } from "./EventOverview";
import { SessionList } from "./sessions/sessionList";
import { Button } from "@/components/ui/button";
import { PlusCircle, UserPlus } from "lucide-react";
import { CreateSessionModal } from "./sessions/CreateSessionModal";
import { RegistrationList } from "./registrations/RegistrationList";
import { CreateRegistrationModal } from "./registrations/CreateRegistrationModal";
import { EventSettingsGeneral } from "./settings/EventSettingsGeneral";
import { useAuthStore } from "@/store/auth.store";

interface EventTabsProps {
  event: NonNullable<GetEventByIdQuery["event"]>;
}

export function EventTabs({ event }: EventTabsProps) {
  const { user } = useAuthStore();
  const [isSessionModalOpen, setIsSessionModalOpen] = useState(false);
  const [isRegModalOpen, setIsRegModalOpen] = useState(false);

  // Show registration button if the event is public or if the user is logged in
  const canRegister = event.isPublic || user;

  return (
    <>
      <CreateSessionModal
        isOpen={isSessionModalOpen}
        onOpenChange={setIsSessionModalOpen}
        eventId={event.id}
        eventStartDate={new Date(event.startDate)}
        eventEndDate={new Date(event.endDate)}
      />
      {canRegister && (
        <CreateRegistrationModal
          isOpen={isRegModalOpen}
          onOpenChange={setIsRegModalOpen}
          eventId={event.id}
        />
      )}

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4 mb-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
          <TabsTrigger value="registrations">Registrations</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <EventOverview
            event={event}
            onRegisterClick={() => setIsRegModalOpen(true)}
          />
        </TabsContent>

        <TabsContent value="sessions" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold">Schedule</h2>
            <Button onClick={() => setIsSessionModalOpen(true)}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Add Session
            </Button>
          </div>
          <SessionList eventId={event.id} />
        </TabsContent>

        <TabsContent value="registrations" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold">Attendees</h2>
            {canRegister && (
              <Button onClick={() => setIsRegModalOpen(true)}>
                <UserPlus className="mr-2 h-4 w-4" />
                Register Attendee
              </Button>
            )}
          </div>
          <RegistrationList eventId={event.id} />
        </TabsContent>

        {/* ✅ NEW SETTINGS TAB */}
        <TabsContent value="settings">
          <EventSettingsGeneral event={event} />
        </TabsContent>
      </Tabs>
    </>
  );
}
