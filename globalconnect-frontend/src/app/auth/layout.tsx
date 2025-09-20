// src/app/auth/layout.tsx
import Link from "next/link";
import Image from "next/image";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          {/* Using the logo you provided */}
          <Link href="/">
            <Image
              src="/logo.png"
              alt="GlobalConnect Logo"
              width={80}
              height={80}
            />
          </Link>
        </div>
        {children}
      </div>
    </div>
  );
}
