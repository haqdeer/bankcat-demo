-- Add is_active flag to commits for de-duping per client/bank/period
ALTER TABLE public.commits
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Ensure vendor_memory unique constraint uses vendor_key
ALTER TABLE public.vendor_memory
DROP CONSTRAINT IF EXISTS vendor_memory_client_vendor_uniq;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'vendor_memory_client_vendor_uniq'
    ) THEN
        ALTER TABLE public.vendor_memory
        ADD CONSTRAINT vendor_memory_client_vendor_uniq
        UNIQUE (client_id, vendor_key);
    END IF;
END $$;
