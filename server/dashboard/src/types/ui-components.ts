import * as React from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  variant?: "default" | "textField" | "nestedInput";
}

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: React.ReactNode;
  containerClassName?: string;
  textareaClassName?: string;
  labelClassName?: string;
}
