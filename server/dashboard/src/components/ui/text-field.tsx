"use client";

import { Calendar, Mail, Search } from "lucide-react";
import * as React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type {
  TextFieldProps,
  NestedInputFieldProps,
  EmailFieldProps,
  SearchFieldProps,
  DateFieldProps,
  DropdownFieldProps,
  DropdownFieldOption,
} from "@/types/ui-components";
import { fieldLabelClassName } from "@/constants/ui-components";

/**
 * textField design spec:
 * - Label: Fustat 12px Semibold, line-height 16px, letter-spacing 0%
 * - Input: h-[38px], rounded-lg, border 1px, py-[10px] px-3,
 *   bg surface-default-primary, border memBorder-primary, text onSurface-default-primary
 * - Gap between label and input: 8px
 * - Default, active, and filled: same styles
 */

const TextField = React.forwardRef<HTMLInputElement, TextFieldProps>(
  (
    {
      label,
      containerClassName,
      inputClassName,
      labelClassName,
      id: idProp,
      className,
      ...props
    },
    ref
  ) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;

    return (
      <div className={cn("flex flex-col gap-1.5", containerClassName)}>
        <Label
          htmlFor={id}
          className={cn(fieldLabelClassName, labelClassName)}
        >
          {label}
        </Label>
        <Input
          ref={ref}
          id={id}
          variant="textField"
          className={cn(inputClassName, className)}
          {...props}
        />
      </div>
    );
  }
);
TextField.displayName = "TextField";

/**
 * nestedInput: same as textField, no icon, 0 border. For use nested inside another container.
 */

const NestedInputField = React.forwardRef<
  HTMLInputElement,
  NestedInputFieldProps
>(
  (
    {
      label,
      containerClassName,
      inputClassName,
      labelClassName,
      id: idProp,
      className,
      ...props
    },
    ref
  ) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;

    return (
      <div className={cn("flex flex-col gap-1.5", containerClassName)}>
        <Label
          htmlFor={id}
          className={cn(fieldLabelClassName, labelClassName)}
        >
          {label}
        </Label>
        <Input
          ref={ref}
          id={id}
          variant="nestedInput"
          className={cn(inputClassName, className)}
          {...props}
        />
      </div>
    );
  }
);
NestedInputField.displayName = "NestedInputField";

/**
 * emailInput: same as textField + Mail icon on the left with color onSurface-default-tertiary.
 */

const EmailField = React.forwardRef<HTMLInputElement, EmailFieldProps>(
  (
    {
      label,
      containerClassName,
      inputClassName,
      labelClassName,
      id: idProp,
      className,
      type = "email",
      showIcon = true,
      ...props
    },
    ref
  ) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;

    return (
      <div className={cn("flex flex-col gap-1.5", containerClassName)}>
        <Label
          htmlFor={id}
          className={cn(fieldLabelClassName, labelClassName)}
        >
          {label}
        </Label>
        <div className="flex h-[38px] w-full min-w-0 items-center rounded-lg border border-memBorder-primary bg-surface-default-primary overflow-hidden">
          {showIcon && (
            <span className="flex shrink-0 items-center pl-3 pr-2 text-onSurface-default-tertiary">
              <Mail className="size-4" />
            </span>
          )}
          <input
            ref={ref}
            id={id}
            type={type}
            className={cn(
              "peer flex flex-1 min-w-0 border-0 bg-transparent py-2.5 font-fustat text-sm text-onSurface-default-primary placeholder:text-onSurface-default-tertiary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium",
              showIcon ? "pl-0 pr-3" : "px-3",
              inputClassName,
              className
            )}
            {...props}
          />
        </div>
      </div>
    );
  }
);
EmailField.displayName = "EmailField";

/**
 * search: same as textField + Search icon on the left with color onSurface-default-primary.
 */

const SearchField = React.forwardRef<HTMLInputElement, SearchFieldProps>(
  (
    {
      label,
      containerClassName,
      inputClassName,
      labelClassName,
      id: idProp,
      className,
      type = "search",
      showIcon = true,
      ...props
    },
    ref
  ) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;

    return (
      <div className={cn("flex flex-col gap-1.5", containerClassName)}>
        {
          label && (
            <Label
              htmlFor={id}
              className={cn(fieldLabelClassName, labelClassName)}
            >
              {label}
            </Label>
          )
        }
        <div className="flex h-[38px] w-full min-w-0 items-center rounded-lg border border-memBorder-primary bg-surface-default-primary overflow-hidden">
          {showIcon && (
            <span className="flex shrink-0 items-center pl-3 pr-2 text-onSurface-default-primary">
              <Search className="size-4" />
            </span>
          )}
          <input
            ref={ref}
            id={id}
            type={type}
            className={cn(
              "peer flex flex-1 min-w-0 border-0 bg-transparent py-2.5 font-fustat text-sm text-onSurface-default-primary placeholder:text-onSurface-default-tertiary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium",
              showIcon ? "pl-0 pr-3" : "px-3",
              inputClassName,
              className
            )}
            {...props}
          />
        </div>
      </div>
    );
  }
);
SearchField.displayName = "SearchField";

/**
 * dateInput: same as textField + Calendar icon on the left with color onSurface-default-tertiary.
 */

const DateField = React.forwardRef<HTMLInputElement, DateFieldProps>(
  (
    {
      label,
      containerClassName,
      inputClassName,
      labelClassName,
      id: idProp,
      className,
      type = "date",
      disabled,
      showIcon = true,
      ...props
    },
    ref
  ) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;
    const inputRef = React.useRef<HTMLInputElement | null>(null);
    const mergedRef = React.useCallback(
      (el: HTMLInputElement | null) => {
        inputRef.current = el;
        if (typeof ref === "function") ref(el);
        else if (ref) (ref as React.MutableRefObject<HTMLInputElement | null>).current = el;
      },
      [ref]
    );

    const handleWrapperClick = () => {
      if (disabled) return;
      const input = inputRef.current;
      if (input?.showPicker) {
        try {
          input.showPicker();
        } catch {
          // showPicker may throw if not triggered by user gesture in some browsers
        }
      }
    };

    return (
      <div className={cn("flex flex-col gap-1.5", containerClassName)}>
        <Label
          htmlFor={id}
          className={cn(fieldLabelClassName, labelClassName)}
        >
          {label}
        </Label>
        <div
          onClick={handleWrapperClick}
          className={cn(
            "flex h-[38px] w-full min-w-0 cursor-pointer items-center rounded-lg border border-memBorder-primary bg-surface-default-primary overflow-hidden",
            disabled && "cursor-not-allowed"
          )}
        >
          {showIcon && (
            <span className="flex shrink-0 items-center pl-3 pr-2 text-onSurface-default-tertiary">
              <Calendar className="size-4" />
            </span>
          )}
          <input
            ref={mergedRef}
            id={id}
            type={type}
            disabled={disabled}
            className={cn(
              "peer flex flex-1 min-w-0 border-0 bg-transparent py-2.5 font-fustat text-onSurface-default-primary placeholder:text-onSurface-default-tertiary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium [&::-webkit-calendar-picker-indicator]:opacity-0",
              showIcon ? "pl-0 pr-3" : "px-3",
              inputClassName,
              className
            )}
            {...props}
          />
        </div>
      </div>
    );
  }
);
DateField.displayName = "DateField";

/**
 * dropdown: same as textField + ChevronDown at end of input with color onSurface-default-primary.
 * Composes Label + Select (SelectTrigger variant=dropdown) + SelectContent.
 */

function DropdownField({
  label,
  placeholder = "Select",
  value,
  onValueChange,
  disabled,
  options,
  containerClassName,
  triggerClassName,
  labelClassName,
  contentClassName,
  selectProps,
}: DropdownFieldProps) {
  const id = React.useId();

  return (
    <div className={cn("flex flex-col gap-1.5", containerClassName)}>
      <Label
        htmlFor={id}
        className={cn(fieldLabelClassName, labelClassName)}
      >
        {label}
      </Label>
      <Select
        value={value}
        onValueChange={onValueChange}
        disabled={disabled}
        {...selectProps}
      >
        <SelectTrigger id={id} variant="dropdown" className={triggerClassName}>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent className={contentClassName}>
          {options.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
DropdownField.displayName = "DropdownField";

export {
  TextField,
  NestedInputField,
  EmailField,
  SearchField,
  DateField,
  DropdownField,
};
export type {
  TextFieldProps,
  NestedInputFieldProps,
  EmailFieldProps,
  SearchFieldProps,
  DateFieldProps,
  DropdownFieldProps,
  DropdownFieldOption,
};
