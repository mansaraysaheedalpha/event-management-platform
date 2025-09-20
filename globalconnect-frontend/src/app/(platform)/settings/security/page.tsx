// src/app/(platform)/settings/security/page.tsx
import { ChangePasswordForm } from "../_components/change-password-form";
import { TwoFactorAuthForm } from "./_components/two-factor-form"; // <-- Import the new component

export default function SecurityPage() {
  return (
    <div className="space-y-8">
      <ChangePasswordForm />
      <TwoFactorAuthForm /> {/* <-- Add it here */}
    </div>
  );
}
