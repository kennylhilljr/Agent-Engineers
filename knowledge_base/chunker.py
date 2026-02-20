"""Chunking strategy for the Knowledge Base RAG pipeline (AI-253).

Splits documents into fixed-size token chunks with overlap so each
chunk fits within an embedding context window.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List


class ChunkingStrategy:
    """Splits text into overlapping chunks suitable for embedding.

    All chunk dicts have the shape::

        {
            "text":        str,   # chunk content
            "start_char":  int,   # byte offset in original text
            "end_char":    int,   # byte offset (exclusive) in original text
            "chunk_index": int,   # 0-based position in chunk list
        }
    """

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token count estimate: 1 token per 4 characters."""
        return len(text) // 4

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 512,
        overlap: int = 64,
    ) -> List[dict]:
        """Split *text* into overlapping chunks of approx *chunk_size* tokens.

        Args:
            text:       Source text to split.
            chunk_size: Target chunk size in tokens (default 512).
            overlap:    Overlap in tokens between consecutive chunks (default 64).

        Returns:
            List of chunk dicts.
        """
        if not text:
            return []

        # Work in characters; convert token limits to char limits.
        # 1 token ~= 4 chars (same formula as estimate_tokens).
        chars_per_chunk = chunk_size * 4
        chars_overlap = overlap * 4

        chunks: List[dict] = []
        start = 0
        chunk_index = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chars_per_chunk, text_len)
            chunk_text = text[start:end]
            chunks.append(
                {
                    "text": chunk_text,
                    "start_char": start,
                    "end_char": end,
                    "chunk_index": chunk_index,
                }
            )
            # Advance by chunk size minus overlap
            advance = chars_per_chunk - chars_overlap
            if advance <= 0:
                advance = 1
            start += advance
            chunk_index += 1

        return chunks

    def chunk_markdown(self, text: str) -> List[dict]:
        """Smart Markdown chunking that respects H1/H2/H3 boundaries.

        Each top-level heading (H1, H2, H3) starts a new chunk.  If a
        section is longer than 512 tokens it is further sub-chunked with
        :meth:`chunk_text`.

        Args:
            text: Markdown source text.

        Returns:
            List of chunk dicts.
        """
        if not text:
            return []

        # Split on H1/H2/H3 headings — keep the heading at the start of each part.
        header_re = re.compile(r"(?m)^(#{1,3} .+)$")
        parts: List[tuple[str, int]] = []  # (section_text, start_char)

        last_start = 0
        for match in header_re.finditer(text):
            if match.start() > last_start:
                parts.append((text[last_start : match.start()], last_start))
            last_start = match.start()
        # Append the final section
        if last_start < len(text):
            parts.append((text[last_start:], last_start))

        # If no headers found, fall back to plain chunking.
        if not parts:
            return self.chunk_text(text)

        result: List[dict] = []
        chunk_index = 0
        for section_text, section_start in parts:
            if not section_text.strip():
                continue
            if self.estimate_tokens(section_text) <= 512:
                result.append(
                    {
                        "text": section_text,
                        "start_char": section_start,
                        "end_char": section_start + len(section_text),
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1
            else:
                # Sub-chunk long sections
                sub_chunks = self.chunk_text(section_text)
                for sub in sub_chunks:
                    result.append(
                        {
                            "text": sub["text"],
                            "start_char": section_start + sub["start_char"],
                            "end_char": section_start + sub["end_char"],
                            "chunk_index": chunk_index,
                        }
                    )
                    chunk_index += 1

        return result

    def chunk_file(self, filepath: str) -> List[dict]:
        """Read *filepath* and chunk it using the appropriate strategy.

        Markdown files (``*.md``) use :meth:`chunk_markdown`; all other
        files use :meth:`chunk_text`.

        Args:
            filepath: Path to the file to chunk.

        Returns:
            List of chunk dicts.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        path = Path(filepath)
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.lower() == ".md":
            return self.chunk_markdown(text)
        return self.chunk_text(text)
