// src/app/(platform)/settings/layout.tsx
import { SettingsNav } from "./_components/settings_nav";

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and organization settings.
        </p>
      </div>
      <SettingsNav />
      <div className="pt-4">{children}</div>
    </div>
  );
}
