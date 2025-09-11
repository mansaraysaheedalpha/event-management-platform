// src/app/(platform)/auth/login/page.tsx (Simplified)
import { LoginForm } from "@/components/features/Auth/LoginForm";
import Link from "next/link";

export default function LoginPage() {
  return (
    <>
      <h2 className="text-2xl font-semibold text-center mb-2">Welcome Back</h2>
      <p className="text-center text-gray-400 mb-6">Sign in to continue.</p>
      <LoginForm />
      <p className="text-center text-sm text-gray-400 mt-6">
        Don't have an account?{" "}
        <Link
          href="/auth/register"
          className="font-semibold text-primary hover:underline"
        >
          Sign Up
        </Link>
      </p>
    </>
  );
}
