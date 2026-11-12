-- Visibility: who may see a published set, chosen by whoever can edit it.
--
--   public   signed-out visitors can View it; signed-in solvers can take it (today's behaviour)
--   private  absent from the public routes and from solvers' /topics; only its editors
--            (admins) can start an attempt on it
--
-- Orthogonal to status: a draft stays invisible whatever this says. Existing sets
-- and new ones default to public, so nothing anyone sees today changes. Attempts
-- already started keep working: they read their own paper, never this column.
ALTER TABLE quiz_sets ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'
  CHECK (visibility IN ('public', 'private'));
