// src/components/features/events/registrations/CreateRegistrationModal.tsx
"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CreateRegistrationForm } from "./CreateRegistrationForm";

interface CreateRegistrationModalProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  eventId: string;
}

export function CreateRegistrationModal({
  isOpen,
  onOpenChange,
  eventId,
}: CreateRegistrationModalProps) {
  const handleFinished = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Register a New Attendee</DialogTitle>
          <DialogDescription>
            Enter the attendee's email. If they are an existing user, they will
            be registered instantly. If not, you can register them as a guest.
          </DialogDescription>
        </DialogHeader>
        <CreateRegistrationForm eventId={eventId} onFinished={handleFinished} />
      </DialogContent>
    </Dialog>
  );
}
