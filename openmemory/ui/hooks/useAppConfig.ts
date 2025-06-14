import { constants } from "@/components/shared/source-app";

export const useAppConfig = (app: { id?: string; name?: string; }) => {
  // First try direct lookup with app.id
  if (app.id && constants[app.id as keyof typeof constants]) {
    return constants[app.id as keyof typeof constants];
  }
  
  // Then try app.name
  if (app.name && constants[app.name as keyof typeof constants]) {
    return constants[app.name as keyof typeof constants];
  }
  
  // Normalize and try variations
  const normalizedName = app.name?.toLowerCase().trim();
  const normalizedId = app.id?.toLowerCase().trim();
  
  const mappings: { [key: string]: keyof typeof constants } = {
    'twitter': 'twitter',
    'x': 'twitter',
    'substack': 'substack',
    'claude': 'claude',
    'openmemory': 'openmemory',
    'jean memory': 'jean memory',
    'cursor': 'cursor',
    'cline': 'cline',
    'roocode': 'roocode',
    'windsurf': 'windsurf',
    'witsy': 'witsy',
    'enconvo': 'enconvo',
    'notion': 'notion',
    'obsidian': 'obsidian'
  };
  
  const constantKey = (normalizedId && mappings[normalizedId]) || (normalizedName && mappings[normalizedName]);
  if (constantKey && constants[constantKey]) {
    return constants[constantKey];
  }
  
  // Fall back to default
  return constants.default;
}; 