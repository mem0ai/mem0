"use client";

import * as React from "react";
import { CalendarIcon } from "@radix-ui/react-icons";
import { format } from "date-fns";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState, useEffect } from "react";

interface DatePickerProps {
  date?: Date;
  onSelect: (date: Date | undefined) => void;
  className?: string;
  maxDate?: Date;
  closeOnSelect?: boolean; // Add this new prop
}

export function DatePicker({
  date,
  onSelect,
  className,
  maxDate,
  closeOnSelect = false, // Add default value
}: DatePickerProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant={"outline"}
          className={cn(
            "w-[100%] justify-start text-left font-normal h-10",
            !date && "text-muted-foreground",
            className,
          )}
        >
          <CalendarIcon className="mr-2 size-4" />
          {date ? format(date, "PPP") : <span>Pick a date</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={date}
          onSelect={(newDate) => {
            onSelect(newDate);
            if (closeOnSelect) {
              setIsOpen(false); // Close the popover if closeOnSelect is true
            }
          }}
          initialFocus
          disabled={(date) => (maxDate ? date > maxDate : false)}
          toDate={maxDate}
        />
      </PopoverContent>
    </Popover>
  );
}
