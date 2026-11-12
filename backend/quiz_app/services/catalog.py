"""The public catalogue: what a signed-out visitor may read. Published sets only, no person's data."""

from __future__ import annotations

from ..errors import NotFound
from ..models import QuizSetInfo, ReviewQuestion
from ..ports import PaperSource, QuizCatalog


class PublicCatalogService:
    def __init__(self, catalog: QuizCatalog, papers: PaperSource):
        self._catalog = catalog
        self._papers = papers

    async def published(self) -> list[QuizSetInfo]:
        return await self._catalog.list_published()

    async def view(self, set_id: int) -> tuple[QuizSetInfo, list[ReviewQuestion]]:
        """A published set with its questions and answer key, in authored order (never shuffled).

        A draft or archived set is indistinguishable from a missing one."""
        info = await self._catalog.get_set(set_id)
        if info is None:
            raise NotFound("quiz set not found")
        return info, await self._papers.paper_source(set_id)
