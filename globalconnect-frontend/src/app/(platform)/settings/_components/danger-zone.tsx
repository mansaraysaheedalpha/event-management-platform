"use client";

import { useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { toast } from "sonner";
import { gql, useMutation } from "@apollo/client";
import { useAuthStore } from "@/store/auth.store";
import { useRouter } from "next/navigation";
import { DELETE_ORGANIZATION_MUTATION } from "./settings.graphql";
import { Loader } from "@/components/ui/loader";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GET_MY_ORGS_QUERY } from "@/graphql/queries";
import { SWITCH_ORG_MUTATION } from "@/graphql/organization.graphql";

interface DangerZoneProps {
  orgName: string;
}

export function DangerZone({ orgName }: DangerZoneProps) {
  const { orgId, logout, setAuth } = useAuthStore();
  const router = useRouter();
  const [confirmName, setConfirmName] = useState("");

  const [switchOrg] = useMutation(SWITCH_ORG_MUTATION, {
    onCompleted: (data) => {
      const { token, user } = data.switchOrganization;
      if (token && user) {
        setAuth(token, user);
        // After switching, go to the dashboard of the new org
        router.push("/dashboard");
      }
    },
    refetchQueries: [{ query: GET_MY_ORGS_QUERY }],
  });

  const [deleteOrganization, { loading }] = useMutation(
    DELETE_ORGANIZATION_MUTATION,
    {
      onCompleted: (data) => {
        const { nextOrganizationId } = data.deleteOrganization;

        if (nextOrganizationId) {
          // If there's another org, switch to it
          toast.success(
            "Organization deleted. Switching to your next organization."
          );
          switchOrg({ variables: { organizationId: nextOrganizationId } });
        } else {
          // If it was the last org, log the user out
          toast.success("Organization deleted. Logging you out.");
          setTimeout(() => {
            logout();
            router.push("/auth/login");
          }, 2000);
        }
      },
      onError: (error) => toast.error(error.message),
    }
  );

  const handleDelete = (isForced: boolean) => {
    deleteOrganization({
      variables: {
        // All variables are now nested inside the 'input' object
        input: {
          organizationId: orgId,
          force: isForced,
        },
      },
    });
  };

  const isConfirmationMatching = confirmName === orgName;

  return (
    <Card className="border-destructive">
      <CardHeader>
        <CardTitle>Danger Zone</CardTitle>
        <CardDescription>
          These actions have serious consequences.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex justify-between items-center">
        <div className="space-y-1">
          <h3 className="font-semibold">Delete organization</h3>
          <p className="text-sm text-muted-foreground">
            Once you delete an organization, there is no going back.
          </p>
        </div>
        <AlertDialog onOpenChange={() => setConfirmName("")}>
          <AlertDialogTrigger asChild>
            <Button variant="destructive">Delete</Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
              <AlertDialogDescription>
                This is a critical action. To confirm, please type{" "}
                <strong className="text-foreground">{orgName}</strong> below.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="space-y-2 py-2">
              <Label htmlFor="confirm-org-name">Organization Name</Label>
              <Input
                id="confirm-org-name"
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
              />
            </div>

            {/* --- THIS IS THE UPDATED FOOTER --- */}
            <AlertDialogFooter className="flex flex-row gap-2 justify-end">
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  variant="outline"
                  onClick={() => handleDelete(false)}
                  disabled={!isConfirmationMatching || loading}
                >
                  {loading && <Loader className="mr-2" />}
                  Schedule Deletion
                </Button>
                <AlertDialogAction
                  onClick={() => handleDelete(true)}
                  disabled={!isConfirmationMatching || loading}
                  className="bg-destructive hover:bg-destructive/90"
                >
                  {loading && <Loader className="mr-2" />}
                  Delete Permanently
                </AlertDialogAction>
              </div>
            </AlertDialogFooter>
            {/* ---------------------------------- */}
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  );
}
