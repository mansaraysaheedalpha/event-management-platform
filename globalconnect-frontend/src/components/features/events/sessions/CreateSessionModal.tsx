"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CreateSessionForm } from "./CreateSessionForm";

interface CreateSessionModalProps {
  eventId: string;
  eventStartDate: Date;
  eventEndDate: Date;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

export function CreateSessionModal({
  isOpen,
  onOpenChange,
  ...rest
}: CreateSessionModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Session</DialogTitle>
          <DialogDescription>
            Fill in the details for the new session. You can assign speakers
            later.
          </DialogDescription>
        </DialogHeader>
        <CreateSessionForm {...rest} onFinished={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
