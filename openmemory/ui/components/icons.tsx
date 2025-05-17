// openmemory/ui/components/icons.tsx
import type React from 'react';

export const Icons = {
  spinner: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`animate-spin ${className}`}
      {...props}
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  ),
  google: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" className={className} {...props} fillRule="evenodd" clipRule="evenodd">
      <title>Google</title>
      <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.85 3.18-1.73 4.1-1.05 1.05-2.36 1.84-4.06 1.84-4.81 0-8.73-3.86-8.73-8.73s3.86-8.73 8.73-8.73c2.43 0 4.5.83 6.18 2.36l-2.65 2.65C16.01 5.36 14.41 4.6 12.48 4.6c-3.93 0-7.2 3.24-7.2 7.2s3.27 7.2 7.2 7.2c4.38 0 6.08-2.96 6.38-4.58h-6.38z" fill="currentColor"/>
    </svg>
  ),
}; 