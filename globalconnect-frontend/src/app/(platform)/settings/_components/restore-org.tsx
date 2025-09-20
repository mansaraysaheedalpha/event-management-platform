"use client";

import { useMutation } from "@apollo/client";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader } from "@/components/ui/loader";
import { RESTORE_ORGANIZATION_MUTATION } from "./settings.graphql";
import { useAuthStore } from "@/store/auth.store";

interface RestoreOrgProps {
  deletionScheduledAt: string;
}

export function RestoreOrg({ deletionScheduledAt }: RestoreOrgProps) {
  const orgId = useAuthStore((state) => state.orgId);

  const [restoreOrganization, { loading }] = useMutation(
    RESTORE_ORGANIZATION_MUTATION,
    {
      onCompleted: () => {
        toast.success("Organization has been restored.");
        // We can simply reload the page to show the normal settings view
        window.location.reload();
      },
      onError: (error) => toast.error(error.message),
    }
  );

  const handleRestore = () => {
    restoreOrganization({ variables: { organizationId: orgId } });
  };

  const formattedDate = new Date(deletionScheduledAt).toLocaleDateString(
    "en-US",
    {
      year: "numeric",
      month: "long",
      day: "numeric",
    }
  );

  return (
    <Card className="border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20">
      <CardHeader>
        <CardTitle className="text-yellow-700 dark:text-yellow-400">
          Pending Deletion
        </CardTitle>
        <CardDescription>
          This organization is scheduled for permanent deletion on{" "}
          <strong>{formattedDate}</strong>.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex justify-between items-center">
        <p className="text-sm">
          You can restore the organization until this date.
        </p>
        <Button onClick={handleRestore} disabled={loading} variant="outline">
          {loading && <Loader className="mr-2" />}
          Restore Organization
        </Button>
      </CardContent>
    </Card>
  );
}
