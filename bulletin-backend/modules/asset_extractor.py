"""
Phase 4: PDF Asset Extraction Service
Episcopal Bulletin Generator

Extracts images, logos, and graphics from existing bulletin PDFs.
Provides SHA256 deduplication, categorization, and an asset library
for reuse in new bulletins.

Tier system (offline-first):
  1. Redis cache for extracted asset metadata
  2. PostgreSQL asset registry
  3. Local filesystem storage (always works)
  4. Paperless-NGX integration (optional OCR pipeline)
"""

import hashlib
import io
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AssetExtractor:
    """Extract and manage image assets from bulletin PDFs."""

    SUPPORTED_FORMATS = {".pdf"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    # Categories for auto-classification
    CATEGORIES = ["logo", "graphic", "photo", "border", "seal", "icon", "unknown"]

    def __init__(
        self,
        asset_dir: Optional[str] = None,
        redis_client=None,
        db_pool=None,
        paperless_url: Optional[str] = None,
    ):
        self.asset_dir = Path(
            asset_dir or os.getenv("ASSET_PATH", "/app/assets")
        )
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        (self.asset_dir / "extracted").mkdir(exist_ok=True)
        (self.asset_dir / "uploads").mkdir(exist_ok=True)
        (self.asset_dir / "thumbnails").mkdir(exist_ok=True)

        self.redis = redis_client
        self.db = db_pool
        self.paperless_url = paperless_url or os.getenv(
            "PAPERLESS_URL", "http://paperless:8000"
        )

        # In-memory manifest (loaded from JSON or built on extract)
        self.manifest: list[dict] = []
        self._load_manifest()

    # ------------------------------------------------------------------
    # Manifest persistence
    # ------------------------------------------------------------------

    def _manifest_path(self) -> Path:
        return self.asset_dir / "manifest.json"

    def _load_manifest(self):
        mp = self._manifest_path()
        if mp.exists():
            try:
                with open(mp, "r", encoding="utf-8-sig") as f:
                    self.manifest = json.load(f)
                logger.info("Loaded asset manifest: %d entries", len(self.manifest))
            except Exception as exc:
                logger.warning("Failed to load manifest: %s", exc)
                self.manifest = []

    def _save_manifest(self):
        with open(self._manifest_path(), "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Core extraction
    # ------------------------------------------------------------------

    def extract_from_pdf(self, pdf_path: str, source_label: str = "") -> dict:
        """
        Extract all images from a PDF file.

        Returns summary dict with extracted count, duplicates skipped, etc.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if pdf_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported file type: {pdf_path.suffix}")

        try:
            import fitz  # PyMuPDF
        except ImportError:
            try:
                import pdfplumber
                return self._extract_with_pdfplumber(pdf_path, source_label)
            except ImportError:
                raise ImportError(
                    "Install PyMuPDF (pip install PyMuPDF) or pdfplumber "
                    "(pip install pdfplumber) for PDF extraction"
                )

        return self._extract_with_pymupdf(pdf_path, source_label)

    def _extract_with_pymupdf(self, pdf_path: Path, source_label: str) -> dict:
        """Primary extraction using PyMuPDF (better image quality)."""
        import fitz

        doc = fitz.open(str(pdf_path))
        extracted = []
        duplicates = 0
        errors = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue

                    image_bytes = base_image["image"]
                    ext = base_image.get("ext", "png")
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)

                    # Skip tiny images (likely artifacts)
                    if width < 20 or height < 20:
                        continue

                    # SHA256 dedup
                    sha256 = hashlib.sha256(image_bytes).hexdigest()
                    if self._is_duplicate(sha256):
                        duplicates += 1
                        continue

                    # Save to extracted dir
                    filename = f"{sha256[:12]}.{ext}"
                    save_path = self.asset_dir / "extracted" / filename
                    with open(save_path, "wb") as f:
                        f.write(image_bytes)

                    # Auto-classify
                    category = self._classify_image(width, height, len(image_bytes))

                    asset_entry = {
                        "id": sha256[:12],
                        "sha256": sha256,
                        "filename": filename,
                        "path": str(save_path),
                        "format": ext,
                        "width": width,
                        "height": height,
                        "size_bytes": len(image_bytes),
                        "category": category,
                        "source_pdf": pdf_path.name,
                        "source_label": source_label or pdf_path.stem,
                        "source_page": page_num + 1,
                        "extracted_date": datetime.now().isoformat(),
                    }

                    self.manifest.append(asset_entry)
                    extracted.append(asset_entry)

                except Exception as exc:
                    logger.warning(
                        "Failed to extract image %d from page %d: %s",
                        img_idx, page_num + 1, exc,
                    )
                    errors += 1

        doc.close()
        self._save_manifest()

        return {
            "source": pdf_path.name,
            "pages_processed": len(doc) if hasattr(doc, '__len__') else 0,
            "images_extracted": len(extracted),
            "duplicates_skipped": duplicates,
            "errors": errors,
            "assets": extracted,
        }

    def _extract_with_pdfplumber(self, pdf_path: Path, source_label: str) -> dict:
        """Fallback extraction using pdfplumber (less image support)."""
        import pdfplumber

        extracted = []
        duplicates = 0

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                for img in page.images:
                    try:
                        # pdfplumber gives bounding boxes; extract raw stream
                        stream = img.get("stream")
                        if stream and hasattr(stream, "get_data"):
                            image_bytes = stream.get_data()
                        else:
                            continue

                        sha256 = hashlib.sha256(image_bytes).hexdigest()
                        if self._is_duplicate(sha256):
                            duplicates += 1
                            continue

                        filename = f"{sha256[:12]}.png"
                        save_path = self.asset_dir / "extracted" / filename
                        with open(save_path, "wb") as f:
                            f.write(image_bytes)

                        w = int(img.get("width", 0))
                        h = int(img.get("height", 0))

                        asset_entry = {
                            "id": sha256[:12],
                            "sha256": sha256,
                            "filename": filename,
                            "path": str(save_path),
                            "format": "png",
                            "width": w,
                            "height": h,
                            "size_bytes": len(image_bytes),
                            "category": self._classify_image(w, h, len(image_bytes)),
                            "source_pdf": pdf_path.name,
                            "source_label": source_label or pdf_path.stem,
                            "source_page": page_num + 1,
                            "extracted_date": datetime.now().isoformat(),
                        }
                        self.manifest.append(asset_entry)
                        extracted.append(asset_entry)

                    except Exception as exc:
                        logger.warning("pdfplumber extract error page %d: %s", page_num + 1, exc)

        self._save_manifest()

        return {
            "source": pdf_path.name,
            "images_extracted": len(extracted),
            "duplicates_skipped": duplicates,
            "assets": extracted,
        }

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _is_duplicate(self, sha256: str) -> bool:
        """Check if this hash already exists in the manifest."""
        return any(a["sha256"] == sha256 for a in self.manifest)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_image(self, width: int, height: int, size_bytes: int) -> str:
        """Heuristic auto-classification based on dimensions and size."""
        aspect = width / max(height, 1)

        # Square-ish and small = likely logo/icon
        if 0.7 < aspect < 1.4 and width < 400:
            return "logo" if size_bytes > 5000 else "icon"

        # Very wide and thin = likely border/rule
        if aspect > 4.0 and height < 50:
            return "border"

        # Large = likely photo or graphic
        if width > 600 and height > 400:
            return "photo"

        # Small square with transparency = likely seal
        if 0.8 < aspect < 1.2 and size_bytes > 20000:
            return "seal"

        return "graphic"

    # ------------------------------------------------------------------
    # Asset management
    # ------------------------------------------------------------------

    def list_assets(
        self,
        category: Optional[str] = None,
        source_pdf: Optional[str] = None,
        max_results: int = 50,
    ) -> list[dict]:
        """List assets with optional filtering."""
        results = list(self.manifest)

        if category:
            results = [a for a in results if a.get("category") == category]
        if source_pdf:
            results = [a for a in results if source_pdf.lower() in a.get("source_pdf", "").lower()]

        return results[:max_results]

    def get_asset(self, asset_id: str) -> Optional[dict]:
        """Get asset metadata by ID (first 12 chars of SHA256)."""
        for a in self.manifest:
            if a.get("id") == asset_id:
                return a
        return None

    def get_asset_bytes(self, asset_id: str) -> Optional[bytes]:
        """Read the raw image bytes for an asset."""
        asset = self.get_asset(asset_id)
        if not asset:
            return None
        asset_path = Path(asset["path"])
        if not asset_path.exists():
            # Try relative to asset_dir
            asset_path = self.asset_dir / "extracted" / asset["filename"]
        if asset_path.exists():
            return asset_path.read_bytes()
        return None

    def recategorize(self, asset_id: str, new_category: str) -> Optional[dict]:
        """Manually recategorize an asset."""
        if new_category not in self.CATEGORIES:
            raise ValueError(f"Invalid category. Use one of: {self.CATEGORIES}")
        for a in self.manifest:
            if a.get("id") == asset_id:
                a["category"] = new_category
                a["recategorized_date"] = datetime.now().isoformat()
                self._save_manifest()
                return a
        return None

    def delete_asset(self, asset_id: str) -> bool:
        """Delete an asset from disk and manifest."""
        asset = self.get_asset(asset_id)
        if not asset:
            return False

        # Remove file
        fpath = Path(asset.get("path", ""))
        if fpath.exists():
            fpath.unlink()

        # Remove from manifest
        self.manifest = [a for a in self.manifest if a.get("id") != asset_id]
        self._save_manifest()
        return True

    def upload_asset(
        self,
        image_bytes: bytes,
        filename: str,
        category: str = "unknown",
        label: str = "",
    ) -> dict:
        """Upload a new asset (not extracted from PDF)."""
        sha256 = hashlib.sha256(image_bytes).hexdigest()

        if self._is_duplicate(sha256):
            existing = next(a for a in self.manifest if a["sha256"] == sha256)
            return {**existing, "status": "duplicate"}

        ext = Path(filename).suffix.lstrip(".") or "png"
        saved_name = f"{sha256[:12]}.{ext}"
        save_path = self.asset_dir / "uploads" / saved_name
        with open(save_path, "wb") as f:
            f.write(image_bytes)

        # Try to get dimensions
        width, height = 0, 0
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
        except Exception:
            pass

        asset_entry = {
            "id": sha256[:12],
            "sha256": sha256,
            "filename": saved_name,
            "path": str(save_path),
            "format": ext,
            "width": width,
            "height": height,
            "size_bytes": len(image_bytes),
            "category": category,
            "source_pdf": "upload",
            "source_label": label or filename,
            "source_page": 0,
            "extracted_date": datetime.now().isoformat(),
            "status": "new",
        }

        self.manifest.append(asset_entry)
        self._save_manifest()
        return asset_entry

    def stats(self) -> dict:
        """Return asset library statistics."""
        categories = {}
        sources = {}
        total_bytes = 0

        for a in self.manifest:
            cat = a.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            src = a.get("source_pdf", "unknown")
            sources[src] = sources.get(src, 0) + 1
            total_bytes += a.get("size_bytes", 0)

        return {
            "total_assets": len(self.manifest),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "by_category": categories,
            "by_source": sources,
            "unique_hashes": len({a["sha256"] for a in self.manifest}),
        }

    # ------------------------------------------------------------------
    # Paperless-NGX integration (optional)
    # ------------------------------------------------------------------

    async def import_from_paperless(self, document_id: int) -> Optional[dict]:
        """
        Fetch a document from Paperless-NGX and extract assets.

        Requires PAPERLESS_URL and Paperless API token.
        """
        try:
            import httpx

            token = os.getenv("PAPERLESS_TOKEN", "")
            headers = {"Authorization": f"Token {token}"} if token else {}

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Download the document
                resp = await client.get(
                    f"{self.paperless_url}/api/documents/{document_id}/download/",
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.warning("Paperless download failed: %d", resp.status_code)
                    return None

                # Save temp PDF
                temp_path = self.asset_dir / f"temp_paperless_{document_id}.pdf"
                with open(temp_path, "wb") as f:
                    f.write(resp.content)

                # Extract assets
                result = self.extract_from_pdf(
                    str(temp_path),
                    source_label=f"paperless-doc-{document_id}",
                )

                # Clean up temp
                temp_path.unlink(missing_ok=True)
                return result

        except ImportError:
            logger.warning("httpx not installed; cannot fetch from Paperless")
            return None
        except Exception as exc:
            logger.warning("Paperless import failed: %s", exc)
            return None
