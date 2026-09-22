"use client";

import { useContext } from "react";
import { AuthContext } from "@/lib/auth";

export function useAuth() {
  return useContext(AuthContext);
}
