CREATE TABLE email_deliveries (
 notification_id uuid PRIMARY KEY REFERENCES notifications(id), owner_id uuid NOT NULL REFERENCES users(id),
 recipient text NOT NULL, status text NOT NULL DEFAULT 'PREPARED', error_code text,
 created_at timestamptz NOT NULL DEFAULT now(), dispatched_at timestamptz, completed_at timestamptz);
