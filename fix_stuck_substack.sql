-- Fix stuck Substack documents that are preventing background processor from completing
-- This clears the needs_chunking flag for documents that are stuck in processing

BEGIN;

-- 1. Find documents stuck in chunking
SELECT 
    d.id,
    d.title,
    d.document_type,
    d.metadata->>'needs_chunking' as needs_chunking,
    d.created_at,
    COUNT(dc.id) as existing_chunks,
    COUNT(m.id) as active_memories
FROM documents d
LEFT JOIN document_chunks dc ON dc.document_id = d.id
LEFT JOIN memories m ON m.metadata->>'document_id' = d.id::text AND m.state = 'active'
WHERE d.metadata->>'needs_chunking' = 'true'
GROUP BY d.id, d.title, d.document_type, d.metadata, d.created_at
ORDER BY d.created_at DESC;

-- 2. Clear chunking flag for documents that already have chunks OR have no active memories
UPDATE documents 
SET metadata = metadata || jsonb_build_object(
    'needs_chunking', false,
    'chunking_cleared_at', NOW()::text,
    'reason', CASE 
        WHEN EXISTS (SELECT 1 FROM document_chunks dc WHERE dc.document_id = documents.id) 
        THEN 'already_has_chunks'
        WHEN NOT EXISTS (SELECT 1 FROM memories m WHERE m.metadata->>'document_id' = documents.id::text AND m.state = 'active')
        THEN 'no_active_memories'
        ELSE 'manual_clear'
    END
)
WHERE metadata->>'needs_chunking' = 'true'
AND (
    -- Either already has chunks
    EXISTS (SELECT 1 FROM document_chunks dc WHERE dc.document_id = documents.id)
    OR
    -- Or has no active memories
    NOT EXISTS (SELECT 1 FROM memories m WHERE m.metadata->>'document_id' = documents.id::text AND m.state = 'active')
);

-- 3. Show results after cleanup
SELECT 
    'After cleanup' as status,
    COUNT(*) as total_documents,
    COUNT(CASE WHEN metadata->>'needs_chunking' = 'true' THEN 1 END) as still_needs_chunking,
    COUNT(CASE WHEN metadata->>'needs_chunking' = 'false' THEN 1 END) as chunking_cleared
FROM documents 
WHERE document_type = 'substack';

COMMIT;

-- Optional: If you want to completely disable background chunking for all Substack content:
-- UPDATE documents SET metadata = metadata || jsonb_build_object('needs_chunking', false, 'disabled_at', NOW()::text) WHERE document_type = 'substack' AND metadata->>'needs_chunking' = 'true'; 