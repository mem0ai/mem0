import { PostHog } from "posthog-node"

export default function PostHogClient() {
  // Return a mock client if no API key is provided (for local development)
  if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) {
    return {
      capture: () => {},
      shutdown: async () => {},
      // Add other methods as needed
    }
  }
  
  const posthogClient = new PostHog(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
    host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
    flushAt: 1,
    flushInterval: 0,
  })
  return posthogClient
}