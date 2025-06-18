-- Add subscription-related columns to the users table

ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR DEFAULT 'free',
ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR,
ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR,
ADD COLUMN IF NOT EXISTS subscription_status VARCHAR DEFAULT 'active',
ADD COLUMN IF NOT EXISTS subscription_current_period_end TIMESTAMPTZ;

-- Add indexes for the new columns
CREATE INDEX IF NOT EXISTS ix_users_subscription_tier ON public.users (subscription_tier);
CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id ON public.users (stripe_customer_id);
CREATE INDEX IF NOT EXISTS ix_users_stripe_subscription_id ON public.users (stripe_subscription_id); 