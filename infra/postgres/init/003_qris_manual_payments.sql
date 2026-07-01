CREATE SCHEMA IF NOT EXISTS billing;

CREATE TABLE IF NOT EXISTS billing.qris_manual_payments
(
    payment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    buyer_email TEXT,
    product_code TEXT,
    amount NUMERIC(18,2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'prepared',
    proof_reference TEXT,
    proof_filename TEXT,
    proof_content_type TEXT,
    proof_size BIGINT,
    payer_name TEXT,
    payment_note TEXT,
    submitted_at TIMESTAMPTZ,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT,
    activation_response JSONB,
    worker_job_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT qris_manual_payments_status_check
    CHECK (status IN ('prepared','submitted','approved','rejected','canceled'))
);

CREATE INDEX IF NOT EXISTS idx_qris_manual_payments_status
ON billing.qris_manual_payments(status, updated_at);

CREATE TABLE IF NOT EXISTS billing.qris_manual_payment_events
(
    event_id BIGSERIAL PRIMARY KEY,
    payment_id TEXT NOT NULL
        REFERENCES billing.qris_manual_payments(payment_id)
        ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor_id TEXT,
    message TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
