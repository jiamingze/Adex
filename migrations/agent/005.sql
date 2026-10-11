ALTER TABLE interactive_plans ADD COLUMN cards jsonb NOT NULL DEFAULT '[]'::jsonb;
