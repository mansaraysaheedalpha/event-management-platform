import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CreateRegistrationForm } from "./CreateRegistrationForm";
import { useAuthStore } from "@/store/auth.store";

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
  const { user } = useAuthStore();

  const handleFinished = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {user ? "Confirm Your Registration" : "Register for this Event"}
          </DialogTitle>
          <DialogDescription>
            {user
              ? `You are registering for this event as ${user.email}. Click below to confirm.`
              : "Provide your details below to register as a guest. If you have an account, please log in."}
          </DialogDescription>
        </DialogHeader>
        <CreateRegistrationForm eventId={eventId} onFinished={handleFinished} />
      </DialogContent>
    </Dialog>
  );
}
