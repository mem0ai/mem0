export type Scope = "project" | "session" | "global";

export interface Mem0Config {
  apiKey: string;
  userId: string;
  autoCapture: boolean;
  defaultScope: Scope;
  contextInjection: boolean;
  searchThreshold: number;
}

export interface ScopeContext {
  userId: string;
  appId: string;
  runId: string;
}

export interface CustomCategory {
  [key: string]: string;
}

export const DEFAULT_CUSTOM_CATEGORIES: CustomCategory[] = [
  { identity: "Personal details, background, and self-descriptions" },
  { preferences: "Likes, dislikes, habits, and preferred ways of doing things" },
  { goals: "Objectives, aspirations, and targets the user is working toward" },
  { projects: "Ongoing work, initiatives, and areas of focus" },
  { decisions: "Choices made, rationale, and trade-offs considered" },
  { technical: "Technical knowledge, tools, configurations, and environment details" },
  { relationships: "People, teams, organizations, and their roles" },
  { routines: "Recurring patterns, workflows, schedules, and processes" },
  { lessons: "Insights learned, mistakes to avoid, and best practices discovered" },
  { work: "Professional context, role, responsibilities, and work environment" },
];
