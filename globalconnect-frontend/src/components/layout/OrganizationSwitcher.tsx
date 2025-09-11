// src/components/layout/OrganizationSwitcher
"use client";

import { useQuery, useMutation, gql, useApolloClient } from "@apollo/client";
import { useAuthStore } from "@/store/auth.store";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { ChevronsUpDown, AlertTriangle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CreateOrgModal } from "./CreateOrgModal"; // <-- Import the modal
import { GET_MY_ORGS_QUERY } from "@/graphql/queries";
import { SWITCH_ORG_MUTATION } from "@/graphql/organization.graphql";

export function OrganizationSwitcher() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const { data, loading, error } = useQuery(GET_MY_ORGS_QUERY);
  const { orgId, setAuth } = useAuthStore();
  const router = useRouter();
  const client = useApolloClient();

  const [switchOrg, { loading: switching }] = useMutation(SWITCH_ORG_MUTATION, {
    onCompleted: (data) => {
      const { token, user } = data.switchOrganization;
      if (token && user) {
        setAuth(token, user);
        client.resetStore();
      }
    },
  });

  const handleSwitch = (newOrgId: string) => {
    if (newOrgId === orgId) return;
    switchOrg({ variables: { organizationId: newOrgId } });
  };

  if (error) {
    console.error("Error fetching organizations:", error);
    return (
      <Button variant="destructive" className="w-56 justify-between">
        <span className="truncate">Error Loading Orgs</span>
        <AlertTriangle className="h-4 w-4 opacity-50" />
      </Button>
    );
  }

  return (
    <>
      {/* 1. The Modal component must be included in the JSX */}
      <CreateOrgModal isOpen={isModalOpen} onOpenChange={setIsModalOpen} />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="w-56 justify-between"
            disabled={loading}
          >
            {/* THIS IS THE CHANGE */}
            <span className="truncate">Switch Organization</span>
            <ChevronsUpDown className="h-4 w-4 opacity-50" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56">
          {/* <DropdownMenuLabel>Switch Organization</DropdownMenuLabel> */}
          <DropdownMenuSeparator />

          {/* 2. The list of organizations to switch to was missing */}
          {data?.myOrganizations.map((org: { id: string; name: string }) => (
            <DropdownMenuItem
              key={org.id}
              onSelect={() => handleSwitch(org.id)}
              disabled={switching}
            >
              {org.name}
            </DropdownMenuItem>
          ))}

          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setIsModalOpen(true)}>
            Create New Organization
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}
