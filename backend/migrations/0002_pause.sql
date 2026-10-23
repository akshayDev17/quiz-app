-- Pause/resume: a nullable paused_at freezes the clock.
--
-- While paused the attempt is still in_progress (open) but not due: the service
-- treats a paused attempt as never expired, and rejects answer writes. Resuming
-- extends deadline_at by the paused duration, so the remaining time is preserved.
-- Untimed attempts have deadline_at = NULL and are never paused.
ALTER TABLE attempts ADD COLUMN paused_at INTEGER;
