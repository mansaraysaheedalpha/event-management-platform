// src/components/ui/description-list.tsx
import { cn } from "@/lib/utils";

// A simple component for clean key-value pair displays
export function DescriptionList({
  title,
  description,
  className,
}: {
  title: React.ReactNode;
  description: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-1.5", className)}>
      <dt className="text-sm font-medium text-muted-foreground">{title}</dt>
      <dd className="text-base font-semibold">{description}</dd>
    </div>
  );
}
