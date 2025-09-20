// src/components/layout/Header.tsx
"use client";

import { useAuthStore } from "@/store/auth.store";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { OrganizationSwitcher } from "./OrganizationSwitcher";
import { useMutation, useQuery } from "@apollo/client";
import { GET_MY_ORGS_QUERY } from "@/graphql/queries";
import { LOGOUT_MUTATION } from "../features/Auth/auth.graphql";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { UserAvatar } from "../ui/user-avatar";
import Link from "next/link";

export function Header() {
  const { user, orgId, logout } = useAuthStore();
  const router = useRouter();
  const { data, loading } = useQuery(GET_MY_ORGS_QUERY);
  const currentOrg = data?.myOrganizations.find((org: any) => org.id === orgId);

  const [logoutUser] = useMutation(LOGOUT_MUTATION, {
    onCompleted: () => {
      logout();
      router.push("/auth/login");
    },
    onError: () => {
      logout();
      router.push("/auth/login");
    },
  });

  return (
    <header className="flex h-16 items-center justify-between border-b bg-secondary/30 px-6">
      <div className="flex items-center gap-4">
        <div className="font-semibold text-lg">
          {loading ? "..." : currentOrg?.name || "Organization"}
        </div>
        <OrganizationSwitcher />
      </div>

      {user ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-3">
              <UserAvatar
                firstName={user.first_name}
                lastName={user.last_name}
                imageUrl={user.imageUrl}
              />
              <div className="text-left hidden md:block">
                <p className="text-sm font-medium">
                  {[user.first_name, user.last_name].filter(Boolean).join(" ")}
                </p>
                <p className="text-xs text-muted-foreground">Organizer</p>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56" align="end">
            <DropdownMenuLabel>My Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <Link href="/settings/profile">
              <DropdownMenuItem>Profile</DropdownMenuItem>
            </Link>
            <Link href="/settings/security">
              <DropdownMenuItem>Security</DropdownMenuItem>
            </Link>
            {/* You can add more links like Billing here later */}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => logoutUser()}>
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <div className="h-9 w-24 animate-pulse rounded-md bg-muted" />
      )}
    </header>
  );
}
