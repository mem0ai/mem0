"""add loops supabase integration trigger

Revision ID: 3a1b2c3d4e5f
Revises: sms_conversation_manual
Create Date: 2024-08-01 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a1b2c3d4e5f'
down_revision: Union[str, None] = 'sms_conversation_manual'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Creates a trigger on auth.users to send webhooks to Loops.so."""
    
    # 1. Ensure pg_net extension is available
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;
    """)

    # 2. Create the function to send webhook
    op.execute("""
    CREATE OR REPLACE FUNCTION public.send_user_to_loops()
    RETURNS TRIGGER AS $$
    DECLARE
      body jsonb;
      record jsonb;
      old_record jsonb;
      loops_url text := 'https://app.loops.so/api/v1/webhooks/supabase/16cc293a78a21ebcf2ad9d37c29fdd4c';
      loops_secret text := 'secret_8a75eea296aa4d0fa591ec6a29045ea';
    BEGIN
      IF (TG_OP = 'INSERT') THEN
        record = to_jsonb(new);
        old_record = null;
      ELSIF (TG_OP = 'UPDATE') THEN
        record = to_jsonb(new);
        old_record = to_jsonb(old);
      ELSIF (TG_OP = 'DELETE') THEN
        record = null;
        old_record = to_jsonb(old);
      END IF;

      body = jsonb_build_object(
          'type', TG_OP,
          'table', TG_TABLE_NAME,
          'schema', TG_TABLE_SCHEMA,
          'record', record,
          'old_record', old_record
      );

      PERFORM net.http_post(
        url:=loops_url,
        headers:=jsonb_build_object(
          'Content-Type', 'application/json',
          'Loops-Secret', loops_secret
        ),
        body:=body,
        timeout_milliseconds:=2000 -- 2 second timeout
      );

      IF (TG_OP = 'DELETE') THEN
        RETURN old;
      END IF;
      RETURN new;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)

    # 3. Create the trigger on the auth.users table
    op.execute("""
    -- Drop trigger if it exists to make this migration re-runnable
    DROP TRIGGER IF EXISTS on_auth_user_change_to_loops ON auth.users;

    CREATE TRIGGER on_auth_user_change_to_loops
      AFTER INSERT OR UPDATE OR DELETE ON auth.users
      FOR EACH ROW EXECUTE PROCEDURE public.send_user_to_loops();
    """)
    
    op.execute("COMMENT ON TRIGGER on_auth_user_change_to_loops ON auth.users IS 'Send user data to Loops.so on user change';")


def downgrade() -> None:
    """Removes the Loops.so integration trigger and function."""
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_change_to_loops ON auth.users;")
    op.execute("DROP FUNCTION IF EXISTS public.send_user_to_loops();") 