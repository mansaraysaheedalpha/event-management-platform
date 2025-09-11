//src / app / platform / settings / _components / settings - nav.tsx;
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export function SettingsNav() {
  const pathname = usePathname();
  const navLinks = [
    { href: "/settings/profile", label: "My Profile" },
    { href: "/settings/security", label: "Security" },
  ];

  return (
    <nav className="flex border-b">
      {navLinks.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={cn(
            "px-4 py-2 -mb-px border-b-2 text-sm font-medium transition-colors",
            pathname === link.href
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
