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
import { useState } from "react";

interface DateTimePickerProps {
  dateTime?: Date;
  onSelect: (dateTime: Date | undefined) => void;
  className?: string;
  maxDate?: Date;
  closeOnSelect?: boolean;
}

export function DateTimePicker({
  dateTime,
  onSelect,
  className,
  maxDate,
  closeOnSelect = false,
}: DateTimePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedTime, setSelectedTime] = useState<string | undefined>(
    undefined,
  );

  const handleTimeSelect = (time: string) => {
    if (dateTime) {
      const [hours, minutes] = time.split(":").map(Number);
      const newDateTime = new Date(dateTime);
      newDateTime.setHours(hours, minutes);
      onSelect(newDateTime);
      setSelectedTime(time);
      if (closeOnSelect) {
        setIsOpen(false);
      }
    }
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant={"outline"}
          className={cn(
            "w-[100%] justify-start text-left font-normal h-10",
            !dateTime && "text-muted-foreground",
            className,
          )}
        >
          <CalendarIcon className="mr-2 size-4" />
          {dateTime ? (
            `${format(dateTime, "PPP")} ${selectedTime ? selectedTime : ""}`
          ) : (
            <span>Pick a date and time</span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={dateTime}
          onSelect={(newDate) => {
            onSelect(newDate);
            if (closeOnSelect) {
              setIsOpen(false);
            }
          }}
          initialFocus
          disabled={(date) => (maxDate ? date > maxDate : false)}
          toDate={maxDate}
        />
        <div className="w-full px-4 pb-4 flex flex-col">
          <span className="text-xs mb-1">Set Time</span>
          {/* Time selection dropdown */}
          <select
            value={selectedTime}
            onChange={(e) => handleTimeSelect(e.target.value)}
          >
            <option value="">Select Time</option>
            {/* Example time options */}
            {Array.from({ length: 24 }, (_, i) => (
              <option key={i} value={`${i}:00`}>{`${i}:00`}</option>
            ))}
          </select>
        </div>
      </PopoverContent>
    </Popover>
  );
}
