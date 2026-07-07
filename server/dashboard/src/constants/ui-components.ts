export const fieldLabelClassName =
  "font-fustat font-semibold text-xs leading-4 tracking-normal text-onSurface-default-tertiary";

export const inputVariants = {
  default:
    "flex h-9 w-full rounded-md border border-memBorder-primary bg-transparent py-2.5 px-3 text-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
  textField:
    "flex h-[38px] w-full min-w-0 rounded-lg border border-memBorder-primary bg-surface-default-primary py-2.5 px-3 font-fustat text-sm text-onSurface-default-primary placeholder:text-onSurface-default-tertiary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium peer",
  nestedInput:
    "flex h-[38px] w-full min-w-0 rounded-lg border-0 bg-transparent py-2.5 px-0 font-fustat text-sm text-onSurface-default-primary placeholder:text-onSurface-default-tertiary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium peer",
} as const;

export const selectTriggerVariants = {
  default:
    "flex h-10 w-full items-center relative justify-between rounded-md border border-memBorder-primary bg-surface-default-primary px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
  dropdown:
    "relative flex h-[38px] w-full min-w-0 items-center justify-between rounded-lg border border-memBorder-primary bg-surface-default-primary py-2.5 pl-3 pr-10 font-fustat text-sm text-onSurface-default-primary placeholder:text-onSurface-default-tertiary focus:outline-none focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50",
} as const;
