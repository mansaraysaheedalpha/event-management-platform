"use client";

import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { useQuery } from "@apollo/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { GET_SPEAKERS_BY_ORG_QUERY } from "@/graphql/speakers.graphql";
import { GetSpeakersByOrgQuery } from "@/gql/graphql";

// Extract the type for a single speaker from our auto-generated query types
type Speaker = GetSpeakersByOrgQuery["organizationSpeakers"][number];

interface SpeakerComboboxProps {
  // `value` will be an array of selected speaker IDs
  value: string[];
  // `onChange` will be called with the new array of IDs
  onChange: (value: string[]) => void;
}

export function SpeakerCombobox({ value, onChange }: SpeakerComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const { data, loading, error } = useQuery(GET_SPEAKERS_BY_ORG_QUERY);

  // Safely access the speakers array, providing a fallback
  const allSpeakers: Speaker[] = data?.organizationSpeakers || [];

  const handleSelect = (speakerId: string) => {
    // Logic to add or remove a speaker from the selection
    const newSelection = value.includes(speakerId)
      ? value.filter((id) => id !== speakerId)
      : [...value, speakerId];
    onChange(newSelection);
  };

  // Find the full speaker objects that correspond to the selected IDs
  const selectedSpeakers = allSpeakers.filter((s) => value.includes(s.id));

  if (error) {
    return <p className="text-sm text-destructive">Could not load speakers.</p>;
  }

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between h-auto min-h-[2.5rem]" // Set min-height for better layout
            disabled={loading}
          >
            <div className="flex flex-wrap gap-1 items-center">
              {selectedSpeakers.length > 0 ? (
                selectedSpeakers.map((s) => (
                  <Badge key={s.id} variant="secondary">
                    {s.name}
                  </Badge>
                ))
              ) : (
                <span className="text-muted-foreground">
                  Select speakers...
                </span>
              )}
            </div>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
          <Command>
            <CommandInput placeholder="Search for a speaker..." />
            <CommandList>
              <CommandEmpty>No speakers found.</CommandEmpty>
              <CommandGroup>
                {allSpeakers.map((speaker) => (
                  <CommandItem
                    key={speaker.id}
                    value={speaker.name}
                    onSelect={() => {
                      handleSelect(speaker.id);
                    }}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        value.includes(speaker.id) ? "opacity-100" : "opacity-0"
                      )}
                    />
                    {speaker.name}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
