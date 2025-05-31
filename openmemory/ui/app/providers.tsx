"use client";

import { Provider } from "react-redux";
import { store } from "../store/store";
import { PostHogProvider } from "../components/PostHogProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <PostHogProvider>
      <Provider store={store}>{children}</Provider>
    </PostHogProvider>
  );
}