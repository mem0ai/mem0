import { Metadata } from "next";
import { DashboardClientLayout } from "./dashboard-client-layout";

export const metadata: Metadata = {
  title: "Dashboard | Mem0",
  description: "Mem0 Dashboard",
};

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <DashboardClientLayout>{children}</DashboardClientLayout>;
}
