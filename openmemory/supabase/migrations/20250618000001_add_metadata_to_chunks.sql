-- Add metadata column to document_chunks table to match the latest backup
ALTER TABLE public.document_chunks
ADD COLUMN IF NOT EXISTS metadata JSONB; 