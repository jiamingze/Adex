CREATE TABLE interactive_tool_results (
 invocation_key text PRIMARY KEY, owner_id uuid NOT NULL, request_hash text NOT NULL,
 result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TRIGGER interactive_tool_result_immutable BEFORE UPDATE OR DELETE ON interactive_tool_results
FOR EACH ROW EXECUTE FUNCTION immutable_interactive_plan();
