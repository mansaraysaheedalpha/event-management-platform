// src/app/(platform)/settings/page.tsx

"use client";

import { useQuery } from "@apollo/client";
import { useAuthStore } from "@/store/auth.store";
import { Loader } from "@/components/ui/loader";
import { OrgProfile } from "./_components/org-profile";
import { DangerZone } from "./_components/danger-zone";
import { RestoreOrg } from "./_components/restore-org";
import { GET_ORGANIZATION_QUERY } from "./_components/settings.graphql";

export default function SettingsPage() {
  const orgId = useAuthStore((state) => state.orgId);

  const { data, loading, error } = useQuery(GET_ORGANIZATION_QUERY, {
    variables: { organizationId: orgId },
    skip: !orgId,
  });

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader className="h-8 w-8" />
      </div>
    );
  }

  if (error || !data?.organization) {
    return (
      <p className="text-destructive">
        Error: Could not load organization data.
      </p>
    );
  }

  const { organization } = data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Organization Settings</h1>
        <p className="text-muted-foreground">
          Manage your organization's details and settings.
        </p>
      </div>

      {organization.status === "PENDING_DELETION" ? (
        <RestoreOrg deletionScheduledAt={organization.deletionScheduledAt} />
      ) : (
        <>
          <OrgProfile />
          <DangerZone orgName={organization.name} />
        </>
      )}
    </div>
  );
}