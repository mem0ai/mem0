import * as React from "react";

import { cn } from "@/lib/utils";
import type { InputProps } from "@/types/ui-components";
import { inputVariants } from "@/constants/ui-components";

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, variant = "default", ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(inputVariants[variant], className)}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input, inputVariants };
export type { InputProps };
