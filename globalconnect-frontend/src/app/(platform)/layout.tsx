// src/app/(platform)/layout.tsx
"use client";

import { useState } from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { CreateOrgModal } from "@/components/layout/CreateOrgModal";

export default function PlatformLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <AuthGuard>
      {/* The modal can now be opened from anywhere inside the layout */}
      <CreateOrgModal isOpen={isModalOpen} onOpenChange={setIsModalOpen} />
      <div className="flex h-screen w-full">
        <Sidebar onOpenCreateOrgModal={() => setIsModalOpen(true)} />{" "}
        {/* Pass down the function */}
        <div className="flex flex-1 flex-col">
          <Header />
          <main className="flex-1 p-6">{children}</main>
        </div>
      </div>
    </AuthGuard>
  );
}