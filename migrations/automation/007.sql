ALTER TABLE schedules DROP CONSTRAINT schedules_task_kind_check;
ALTER TABLE schedules ADD CONSTRAINT schedules_task_kind_check
 CHECK(task_kind IN ('CHAT','CONNECTOR_SYNC','MATRIX_REMINDER'));
