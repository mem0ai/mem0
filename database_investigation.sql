-- 🕵️ Comprehensive Database Contamination Investigation
-- Looking for patterns of cross-user memory contamination

-- 1. Search for memories containing the specific UUID mentioned: 69785a2c-1c2e-59e4-8490-a44d68f1da49
SELECT 
    'SEARCH FOR SPECIFIC UUID' as investigation_type,
    u.user_id as affected_user_uuid,
    u.email as affected_user_email,
    m.id as memory_id,
    m.content,
    m.created_at,
    a.name as app_name
FROM memories m
JOIN users u ON m.user_id = u.id
JOIN apps a ON m.app_id = a.id
WHERE 
    m.state != 'deleted' 
    AND (
        LOWER(m.content) LIKE '%69785a2c-1c2e-59e4-8490-a44d68f1da49%'
        OR LOWER(m.content) LIKE '%69785a2c%'
        OR LOWER(m.content) LIKE '%pralay%'
    )
ORDER BY m.created_at DESC;

-- 2. Look for potential username/path leakage patterns
SELECT 
    'USERNAME PATH LEAKAGE' as investigation_type,
    u.user_id as affected_user_uuid,
    u.email as affected_user_email,
    COUNT(*) as suspicious_memories,
    MIN(m.created_at) as first_occurrence,
    MAX(m.created_at) as last_occurrence,
    CASE 
        WHEN COUNT(*) > 10 THEN 'HIGH RISK'
        WHEN COUNT(*) > 5 THEN 'MEDIUM RISK'
        ELSE 'LOW RISK'
    END as risk_level
FROM memories m
JOIN users u ON m.user_id = u.id
WHERE 
    m.state != 'deleted' 
    AND (
        LOWER(m.content) LIKE '%/users/%'
        OR LOWER(m.content) LIKE '%/home/%'
        OR LOWER(m.content) LIKE '%c:\\users\\%'
        OR LOWER(m.content) LIKE '%documents and settings%'
    )
GROUP BY u.user_id, u.email
HAVING COUNT(*) > 0
ORDER BY suspicious_memories DESC;

-- 3. Check for development-specific contamination patterns
SELECT 
    'DEVELOPMENT CONTAMINATION' as investigation_type,
    u.user_id as affected_user_uuid,
    u.email as affected_user_email,
    COUNT(*) as dev_memories,
    STRING_AGG(DISTINCT 
        CASE 
            WHEN LOWER(m.content) LIKE '%junit%' THEN 'junit'
            WHEN LOWER(m.content) LIKE '%maven%' THEN 'maven'
            WHEN LOWER(m.content) LIKE '%gradle%' THEN 'gradle'
            WHEN LOWER(m.content) LIKE '%spring%' THEN 'spring'
            WHEN LOWER(m.content) LIKE '%@test%' THEN 'test_annotations'
            WHEN LOWER(m.content) LIKE '%assertequals%' THEN 'assert_methods'
            WHEN LOWER(m.content) LIKE '%pickgroup%' THEN 'pickgroup_specific'
            WHEN LOWER(m.content) LIKE '%rebin%' THEN 'rebin_specific'
        END, ', '
    ) as dev_patterns
FROM memories m
JOIN users u ON m.user_id = u.id
WHERE 
    m.state != 'deleted' 
    AND (
        LOWER(m.content) LIKE '%junit%'
        OR LOWER(m.content) LIKE '%maven%'
        OR LOWER(m.content) LIKE '%gradle%'
        OR LOWER(m.content) LIKE '%spring%'
        OR LOWER(m.content) LIKE '%@test%'
        OR LOWER(m.content) LIKE '%assertequals%'
        OR LOWER(m.content) LIKE '%pickgroup%'
        OR LOWER(m.content) LIKE '%rebin%'
        OR LOWER(m.content) LIKE '%abstractentityid%'
        OR LOWER(m.content) LIKE '%centeridtest%'
    )
GROUP BY u.user_id, u.email
HAVING COUNT(*) > 0
ORDER BY dev_memories DESC;

-- 4. Timeline analysis of contamination
SELECT 
    'CONTAMINATION TIMELINE' as investigation_type,
    DATE(m.created_at) as contamination_date,
    COUNT(*) as suspicious_memories_created,
    COUNT(DISTINCT u.user_id) as users_affected,
    COUNT(DISTINCT a.id) as apps_affected,
    STRING_AGG(DISTINCT u.email, ', ') as affected_emails
FROM memories m
JOIN users u ON m.user_id = u.id
JOIN apps a ON m.app_id = a.id
WHERE 
    m.state != 'deleted' 
    AND (
        LOWER(m.content) LIKE '%/users/%'
        OR LOWER(m.content) LIKE '%pralayb%'
        OR LOWER(m.content) LIKE '%pralay%'
        OR LOWER(m.content) LIKE '%faircopyfolder%'
        OR LOWER(m.content) LIKE '%pick-planning%'
        OR LOWER(m.content) LIKE '%junit%'
        OR LOWER(m.content) LIKE '%assertequals%'
    )
GROUP BY DATE(m.created_at)
HAVING COUNT(*) > 0
ORDER BY contamination_date DESC;

-- 5. Check if the real pralay user exists
SELECT 
    'REAL PRALAY USER CHECK' as investigation_type,
    u.user_id,
    u.email,
    u.name,
    u.created_at as user_created,
    COUNT(m.id) as total_memories,
    COUNT(CASE WHEN LOWER(m.content) LIKE '%pralay%' THEN 1 END) as self_referencing,
    COUNT(CASE WHEN LOWER(m.content) LIKE '%pralayb%' THEN 1 END) as username_mentions,
    COUNT(CASE WHEN LOWER(m.content) LIKE '%/users/pralayb%' THEN 1 END) as path_mentions
FROM users u
LEFT JOIN memories m ON u.id = m.user_id AND m.state != 'deleted'
WHERE 
    LOWER(u.email) LIKE '%pralay%' 
    OR LOWER(u.name) LIKE '%pralay%'
    OR u.user_id LIKE '%69785a2c%'
    OR u.user_id = '69785a2c-1c2e-59e4-8490-a44d68f1da49'
GROUP BY u.user_id, u.email, u.name, u.created_at;

-- 6. Session/app analysis for contamination sources
SELECT 
    'APP CONTAMINATION ANALYSIS' as investigation_type,
    a.name as app_name,
    a.id as app_id,
    COUNT(DISTINCT u.user_id) as users_with_suspicious_content,
    COUNT(*) as suspicious_memories,
    MIN(m.created_at) as first_suspicious,
    MAX(m.created_at) as last_suspicious
FROM memories m
JOIN users u ON m.user_id = u.id
JOIN apps a ON m.app_id = a.id
WHERE 
    m.state != 'deleted' 
    AND (
        LOWER(m.content) LIKE '%pralayb%'
        OR LOWER(m.content) LIKE '%/users/%'
        OR LOWER(m.content) LIKE '%faircopyfolder%'
        OR LOWER(m.content) LIKE '%pick-planning%'
    )
GROUP BY a.name, a.id
ORDER BY suspicious_memories DESC;

-- 7. Memory access pattern analysis
SELECT 
    'MEMORY ACCESS PATTERNS' as investigation_type,
    mal.access_type,
    COUNT(*) as access_count,
    COUNT(DISTINCT mal.memory_id) as unique_memories,
    COUNT(DISTINCT m.user_id) as unique_users,
    MIN(mal.created_at) as first_access,
    MAX(mal.created_at) as last_access
FROM memory_access_logs mal
JOIN memories m ON mal.memory_id = m.id
WHERE mal.created_at >= NOW() - INTERVAL 7 DAY  -- Last 7 days
GROUP BY mal.access_type
ORDER BY access_count DESC;

-- 8. Summary of contamination scope
SELECT 
    'CONTAMINATION SUMMARY' as report_section,
    (SELECT COUNT(*) FROM memories WHERE state != 'deleted' AND (
        LOWER(content) LIKE '%pralayb%' 
        OR LOWER(content) LIKE '%/users/%'
        OR LOWER(content) LIKE '%faircopyfolder%'
    )) as total_suspicious_memories,
    (SELECT COUNT(DISTINCT user_id) FROM memories WHERE state != 'deleted' AND (
        LOWER(content) LIKE '%pralayb%' 
        OR LOWER(content) LIKE '%/users/%'
        OR LOWER(content) LIKE '%faircopyfolder%'
    )) as users_affected,
    (SELECT COUNT(*) FROM users) as total_users,
    (SELECT COUNT(*) FROM memories WHERE state != 'deleted') as total_active_memories,
    ROUND(
        (SELECT COUNT(*) FROM memories WHERE state != 'deleted' AND (
            LOWER(content) LIKE '%pralayb%' 
            OR LOWER(content) LIKE '%/users/%'
            OR LOWER(content) LIKE '%faircopyfolder%'
        )) * 100.0 / NULLIF((SELECT COUNT(*) FROM memories WHERE state != 'deleted'), 0), 
        2
    ) as contamination_percentage; 