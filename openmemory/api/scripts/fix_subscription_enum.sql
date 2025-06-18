-- Fix subscription tier enum issue in production
-- This script fixes the case mismatch between Python enum and database values

-- Step 1: Update any lowercase values to uppercase (if the column exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name='users' AND column_name='subscription_tier') THEN
        
        -- Fix lowercase values
        UPDATE users SET subscription_tier = 'FREE' WHERE subscription_tier = 'free';
        UPDATE users SET subscription_tier = 'PRO' WHERE subscription_tier = 'pro';
        UPDATE users SET subscription_tier = 'ENTERPRISE' WHERE subscription_tier = 'enterprise';
        
        RAISE NOTICE 'Updated subscription tier values to uppercase';
    ELSE
        RAISE NOTICE 'subscription_tier column does not exist yet';
    END IF;
END $$;

-- Step 2: Check current values
SELECT 'Current subscription tier values:' as info;
SELECT subscription_tier, COUNT(*) as count 
FROM users 
WHERE subscription_tier IS NOT NULL 
GROUP BY subscription_tier; 