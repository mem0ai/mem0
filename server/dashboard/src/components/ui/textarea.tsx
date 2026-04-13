import * as React from "react";

import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";
import { fieldLabelClassName } from "@/constants/ui-components";
import { TextareaProps } from "@/types/ui-components";

/**
 * Same style as default input (textField): rounded-lg, border-memBorder-primary,
 * bg-surface-default-primary, font-fustat, text-onSurface-default-primary. Height 129px.
 */
const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      containerClassName,
      textareaClassName,
      labelClassName,
      id: idProp,
      className,
      ...props
    },
    ref,
  ) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;

    const textarea = (
      <textarea
        id={id}
        className={cn(
          "flex h-[129px] w-full min-w-0 rounded-lg border border-memBorder-primary bg-surface-default-primary px-3 py-2.5 font-fustat text-sm text-onSurface-default-primary placeholder:text-onSurface-default-tertiary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition-colors resize-none",
          textareaClassName,
          className,
        )}
        ref={ref}
        {...props}
      />
    );

    if (label) {
      return (
        <div className={cn("flex flex-col gap-1.5", containerClassName)}>
          <Label
            htmlFor={id}
            className={cn(fieldLabelClassName, labelClassName)}
          >
            {label}
          </Label>
          {textarea}
        </div>
      );
    }

    return textarea;
  },
);
Textarea.displayName = "Textarea";

export { Textarea };
