import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

type TypographyVariant =
  | "h1"
  | "h2"
  | "h3"
  | "h4"
  | "h5"
  | "body-lg"
  | "body"
  | "body-sm"
  | "body-xs"
  | "caption"
  | "caption-sm"
  | "overline";

type TypographyElement = "h1" | "h2" | "h3" | "h4" | "h5" | "p" | "span";

/**
 * Typography system – use typo-* classes or these components.
 *
 * Tokens:
 * - h1–h5, body-lg, body, body-sm, body-xs: Fustat
 * - caption, caption-sm, overline: DM Mono
 */
const typographyVariants = cva("", {
  variants: {
    variant: {
      h1: "typo-h1",
      h2: "typo-h2",
      h3: "typo-h3",
      h4: "typo-h4",
      h5: "typo-h5",
      "body-lg": "typo-body-lg",
      body: "typo-body",
      "body-sm": "typo-body-sm",
      "body-xs": "typo-body-xs",
      caption: "typo-caption",
      "caption-sm": "typo-caption-sm",
      overline: "typo-overline",
    },
  },
  defaultVariants: {
    variant: "body",
  },
});

const variantToElement: Record<TypographyVariant, TypographyElement> = {
  h1: "h1",
  h2: "h2",
  h3: "h3",
  h4: "h4",
  h5: "h5",
  "body-lg": "p",
  body: "p",
  "body-sm": "p",
  "body-xs": "span",
  caption: "span",
  "caption-sm": "span",
  overline: "span",
};

export interface TypographyProps
  extends
    React.HTMLAttributes<HTMLElement>,
    VariantProps<typeof typographyVariants> {
  as?: TypographyElement;
}

const Typography = React.forwardRef<HTMLElement, TypographyProps>(
  ({ className, variant = "body", as, ...props }, ref) => {
    const Comp = as ?? (variant ? variantToElement[variant] : "p");
    return (
      <Comp
        className={cn(typographyVariants({ variant }), className)}
        ref={ref as any}
        {...props}
      />
    );
  },
);
Typography.displayName = "Typography";

export { Typography, typographyVariants };
