-- Add is_active flag to commits for de-duping per client/bank/period
ALTER TABLE public.commits
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Ensure vendor_memory unique constraint uses correct column
ALTER TABLE public.vendor_memory
DROP CONSTRAINT IF EXISTS vendor_memory_client_vendor_uniq;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'vendor_memory'
          AND column_name = 'vendor'
    ) THEN
        ALTER TABLE public.vendor_memory
        ADD CONSTRAINT vendor_memory_client_vendor_uniq
        UNIQUE (client_id, vendor);
    ELSE
        ALTER TABLE public.vendor_memory
        ADD CONSTRAINT vendor_memory_client_vendor_uniq
        UNIQUE (client_id, vendor_name);
    END IF;
END $$;
