-- Preserve historical selectors while admitting the current Qwen default.
-- NOT VALID avoids scanning history under the constraint replacement lock;
-- validation still checks existing rows before this migration commits.
ALTER TABLE turns DROP CONSTRAINT turns_model_check;
ALTER TABLE turns ADD CONSTRAINT turns_model_check
    CHECK (model IN ('', 'qwen3.8-max', 'qwen3.8-flash', 'minimax')) NOT VALID;
ALTER TABLE turns VALIDATE CONSTRAINT turns_model_check;
