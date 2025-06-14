"use client";

import { motion } from "framer-motion";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";

function TemplateContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [shouldAnimate, setShouldAnimate] = useState(false);

  useEffect(() => {
    // Check if we're on the auth page with the animate parameter
    const shouldAnimateFromUrl = pathname === "/auth" && searchParams.get('animate') === 'true';
    
    console.log('Template Debug:', {
      pathname,
      animateParam: searchParams.get('animate'),
      shouldAnimateFromUrl
    });
    
    setShouldAnimate(shouldAnimateFromUrl);
  }, [pathname, searchParams]);

  // If we should animate (landing to auth transition), use the swipe animation
  if (shouldAnimate) {
    console.log('Applying slide animation');
    return (
      <motion.div
        initial={{ x: "100%", opacity: 0 }}
        animate={{ x: "0%", opacity: 1 }}
        exit={{ x: "-100%", opacity: 0 }}
        transition={{ ease: "easeInOut", duration: 0.75 }}
      >
        {children}
      </motion.div>
    );
  }

  console.log('No animation - rendering instantly');
  // For all other transitions, render instantly without animation
  return <>{children}</>;
}

export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<>{children}</>}>
      <TemplateContent>{children}</TemplateContent>
    </Suspense>
  );
} 