import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DescriptionList } from "@/components/ui/description-list";
import { Button } from "@/components/ui/button";
import { GetEventByIdQuery } from "@/gql/graphql";
import { useAuthStore } from "@/store/auth.store";
import { format } from "date-fns";
import { UserPlus } from "lucide-react";

type EventDetails = NonNullable<GetEventByIdQuery["event"]>;

interface EventOverviewProps {
  event: EventDetails;
  onRegisterClick: () => void;
}

export function EventOverview({ event, onRegisterClick }: EventOverviewProps) {
  const { user } = useAuthStore();
  const canRegister = event.isPublic || user;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Event Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {event.description && (
          <DescriptionList
            title="Description"
            description={event.description}
          />
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <DescriptionList
            title="Start Date"
            description={format(new Date(event.startDate), "PPP p")}
          />
          <DescriptionList
            title="End Date"
            description={format(new Date(event.endDate), "PPP p")}
          />
          <DescriptionList
            title="Visibility"
            description={event.isPublic ? "Public" : "Private"}
          />
        </div>
      </CardContent>
      {canRegister && (
        <CardFooter>
          <Button onClick={onRegisterClick} size="lg">
            <UserPlus className="mr-2 h-5 w-5" />
            Register for this Event
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}
