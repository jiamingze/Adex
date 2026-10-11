CREATE TABLE interactive_plans (
 invocation_key text PRIMARY KEY, owner_id uuid NOT NULL, context_hash text NOT NULL,
 messages jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE FUNCTION immutable_interactive_plan() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Interactive plans are immutable'; END $$;
CREATE TRIGGER interactive_plan_immutable BEFORE UPDATE OR DELETE ON interactive_plans
FOR EACH ROW EXECUTE FUNCTION immutable_interactive_plan();
