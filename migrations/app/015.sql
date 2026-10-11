ALTER TABLE turns ADD COLUMN model text NOT NULL DEFAULT '' CHECK (model IN ('','qwen3.8-max','minimax'));
