import * as React from "react";
import { type VariantProps } from "class-variance-authority";
import { Select } from "@/components/ui/select";

/**
 * TextField component props
 */
export interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: React.ReactNode;
  containerClassName?: string;
  inputClassName?: string;
  labelClassName?: string;
}

/**
 * NestedInputField component props
 */
export interface NestedInputFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: React.ReactNode;
  containerClassName?: string;
  inputClassName?: string;
  labelClassName?: string;
}

/**
 * EmailField component props
 */
export interface EmailFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: React.ReactNode;
  containerClassName?: string;
  inputClassName?: string;
  labelClassName?: string;
  showIcon?: boolean;
}

/**
 * SearchField component props
 */
export interface SearchFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: React.ReactNode;
  containerClassName?: string;
  inputClassName?: string;
  labelClassName?: string;
  showIcon?: boolean;
}

/**
 * DateField component props
 */
export interface DateFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: React.ReactNode;
  containerClassName?: string;
  inputClassName?: string;
  labelClassName?: string;
  showIcon?: boolean;
}

/**
 * Textarea component props
 */
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: React.ReactNode;
  containerClassName?: string;
  textareaClassName?: string;
  labelClassName?: string;
}

/**
 * DropdownField option type
 */
export interface DropdownFieldOption {
  value: string;
  label: React.ReactNode;
}

/**
 * DropdownField component props
 */
export interface DropdownFieldProps {
  label: React.ReactNode;
  placeholder?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
  options: DropdownFieldOption[];
  containerClassName?: string;
  triggerClassName?: string;
  labelClassName?: string;
  contentClassName?: string;
  /** Select root props: name, required, onOpenChange, open, defaultValue */
  selectProps?: Omit<
    React.ComponentPropsWithoutRef<typeof Select>,
    "value" | "onValueChange" | "disabled"
  >;
}

/**
 * Input component props
 */
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  variant?: "default" | "textField" | "nestedInput";
}

/**
 * Button component props
 * Note: ButtonProps is defined in @/components/ui/button and exported from there
 * due to dependency on buttonVariants. Import ButtonProps from @/components/ui/button
 */
