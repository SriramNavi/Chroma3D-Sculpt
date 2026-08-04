from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPOSITORY_ROOT / "datasets" / "statues"
RAW_ROOT = DATASET_ROOT / "raw"
PROCESSED_ROOT = DATASET_ROOT / "processed"
METADATA_ROOT = DATASET_ROOT / "metadata"
THUMBNAIL_ROOT = DATASET_ROOT / "thumbnails"
MANIFEST_ROOT = DATASET_ROOT / "manifests"
LICENSE_ROOT = DATASET_ROOT / "licenses"

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "Chroma3D-Sculpt-Real-Statue-Dataset/1.0 "
    "(dataset validation; https://github.com/; no automated scraping)"
)
DATASET_VERSION = "1.0.0"

ALLOWED_LICENSES = {
    "CC0": {
        "identifier": "CC0-1.0",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "legal_text_url": (
            "https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt"
        ),
        "local_file": "CC0-1.0.txt",
    },
    "CC BY 4.0": {
        "identifier": "CC-BY-4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "legal_text_url": "https://creativecommons.org/licenses/by/4.0/legalcode.txt",
        "local_file": "CC-BY-4.0.txt",
    },
    "CC BY-SA 4.0": {
        "identifier": "CC-BY-SA-4.0",
        "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "legal_text_url": (
            "https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt"
        ),
        "local_file": "CC-BY-SA-4.0.txt",
    },
}


@dataclass(frozen=True)
class CuratedAsset:
    unique_id: str
    commons_title: str
    title: str
    subject: str
    category: str
    religious_cultural_classification: str
    expected_license: str
    original_repository: str
    notes: tuple[str, ...]
    author_override: str | None = None


CURATED_ASSETS = (
    CuratedAsset(
        "statue-ganesha-java-10c",
        "File:Ganesha, 10th - 11th C CE - 3D model by Minneapolis Institute of Art - Sketchfab.stl",
        "Ganesha, 10th–11th century CE",
        "Ganesha seated on a double-lotus base",
        "full_statue",
        "Hindu; Javanese; Indonesia",
        "CC0",
        "Minneapolis Institute of Art via Sketchfab and Wikimedia Commons",
        ("Volcanic-stone museum object scan.",),
    ),
    CuratedAsset(
        "statue-uma-maheshvara-java-10c",
        "File:Uma-Maheshvara, 10th - 11th C CE - 3D model by Minneapolis Institute of Art - Sketchfab.stl",
        "Uma-Maheshvara, 10th–11th century CE",
        "Shiva and Uma with Ganesha, Skanda, and Nandi",
        "deity_group",
        "Hindu; South Asian/Javanese",
        "CC0",
        "Minneapolis Institute of Art via Sketchfab and Wikimedia Commons",
        ("Sandstone museum object scan with multiple figures and attributes.",),
    ),
    CuratedAsset(
        "statue-cosmic-buddha-smithsonian-150k",
        "File:Cosmic-buddha-laser-scan-150k (Smithsonian Institution).stl",
        "Cosmic Buddha, 150k laser scan",
        "Buddha draped in robes portraying the Realms of Existence",
        "full_statue",
        "Buddhist; Chinese; Northern Qi dynasty",
        "CC0",
        "Smithsonian Institution via Wikimedia Commons",
        ("Decimated 150k-mesh derivative selected instead of the 2.88 GiB source.",),
    ),
    CuratedAsset(
        "statue-hotei-water-basin",
        "File:Ana-Hachimangu water basin of Hotei 2024-04-25.stl",
        "Ana-Hachimangu Hotei water basin",
        "Hotei figure incorporated into a water basin",
        "functional_sculpture",
        "Buddhist folklore; Japanese",
        "CC0",
        "Independent photogrammetry via Wikimedia Commons",
        ("Outdoor weathered sculpture scan.",),
    ),
    CuratedAsset(
        "statue-asad-al-lat",
        "File:Asad Al-Lat.stl",
        "Asad Al-Lat",
        "Lion of Al-Lat digital reconstruction",
        "monument_reconstruction",
        "Ancient Syrian/Palmyrene religious heritage",
        "CC0",
        "NEWPALMYRA / Re-Sculpting Syrian Statues Digitally via Wikimedia Commons",
        ("Digitally reconstructed heritage statue; useful low-size topology case.",),
    ),
    CuratedAsset(
        "statue-bastet",
        "File:Thingiverse - Bastet.stl",
        "Bastet",
        "Egyptian goddess Bastet",
        "figurine",
        "Ancient Egyptian religion",
        "CC BY 4.0",
        "Thingiverse via Wikimedia Commons",
        ("Small stylized statue representing a low-complexity regression case.",),
    ),
    CuratedAsset(
        "statue-castlestrange-stone",
        "File:Castlestrange Stone - 3D model by roscommon3d - Sketchfab.stl",
        "Castlestrange Stone",
        "Iron Age carved stone",
        "ornamental_stone",
        "Iron Age Celtic; Ireland",
        "CC0",
        "roscommon3d via Sketchfab and Wikimedia Commons",
        ("Carved stone provides a non-figurative sculptural surface case.",),
    ),
    CuratedAsset(
        "statue-caracalla-bust",
        "File:Bust of Emperor Caracalla.stl",
        "Bust of Emperor Caracalla",
        "Roman imperial portrait bust",
        "bust",
        "Ancient Roman",
        "CC0",
        "Independent scan via Wikimedia Commons",
        ("Compact portrait-bust regression case.",),
    ),
    CuratedAsset(
        "statue-greek-slave-smithsonian-150k",
        "File:Greek-slave-plaster-cast-150k (Smithsonian Institution).stl",
        "The Greek Slave, 150k plaster cast",
        "Plaster cast of Hiram Powers' The Greek Slave",
        "full_statue",
        "Neoclassical; United States",
        "CC0",
        "Smithsonian American Art Museum via Wikimedia Commons",
        ("Museum-provided decimated scan.",),
    ),
    CuratedAsset(
        "statue-danaid-rodin",
        "File:Danaid NMSk 1854 (Auguste Rodin) - Nationalmuseum - 76c5c234c6074b13a94bf793c276a509.stl",
        "Danaid",
        "Crouching Danaid by Auguste Rodin",
        "full_statue",
        "Greek mythology; European modern sculpture",
        "CC BY 4.0",
        "Nationalmuseum via Wikimedia Commons",
        ("Terracotta sculpture scan with a low, wide pose.",),
    ),
    CuratedAsset(
        "statue-david-michelangelo",
        "File:David (Michelangelo).stl",
        "David",
        "Michelangelo's David",
        "full_statue",
        "Biblical; Italian Renaissance",
        "CC BY-SA 4.0",
        "Scan the World via Wikimedia Commons",
        ("High-detail full-body photogrammetry/structured-light model.",),
    ),
    CuratedAsset(
        "statue-icarus-ioannidou",
        "File:Icarus sculpture (Yiota Ioannidou).stl",
        "Icarus",
        "Icarus sculpture by Yiota Ioannidou",
        "full_statue",
        "Greek mythology; contemporary Cypriot sculpture",
        "CC BY-SA 4.0",
        "Independent scan via Wikimedia Commons",
        ("Contemporary public-sculpture scan.",),
    ),
    CuratedAsset(
        "statue-laurana-woman-bust",
        "File:Laurana.stl",
        "Woman by Francesco Laurana",
        "Bust of a woman after a marble original",
        "bust",
        "Italian Renaissance",
        "CC BY-SA 4.0",
        "CNR cast digitization via Wikimedia Commons",
        ("Early structured-light digitization of a museum cast.",),
    ),
    CuratedAsset(
        "statue-hercules-archer-mia",
        "File:Pierre Puget's Hercules as Archer - 3D model by Minneapolis Institute of Art - Sketchfab.stl",
        "Hercules as Archer",
        "Pierre Puget's Hercules as Archer",
        "full_statue",
        "Greco-Roman mythology; French Baroque",
        "CC0",
        "Minneapolis Institute of Art via Sketchfab and Wikimedia Commons",
        ("Museum object scan with extended limbs and weapon detail.",),
    ),
    CuratedAsset(
        "statue-belvedere-torso",
        "File:Scan the World - Belvedere Torso.stl",
        "Belvedere Torso",
        "Fragmentary male torso",
        "fragment",
        "Classical Greco-Roman",
        "CC BY-SA 4.0",
        "Scan the World via Wikimedia Commons",
        ("Fragmentary sculpture for incomplete-form regression coverage.",),
    ),
    CuratedAsset(
        "statue-juno-ludovisi",
        "File:Scan the World - Juno Ludovisi.stl",
        "Juno Ludovisi",
        "Colossal head associated with Juno",
        "head",
        "Ancient Roman religion",
        "CC BY-SA 4.0",
        "Scan the World via Wikimedia Commons",
        ("Large sculpted-head form.",),
    ),
    CuratedAsset(
        "statue-laocoon-group",
        "File:Scan the World - Laocoon Group.stl",
        "Laocoön Group",
        "Laocoön and his sons",
        "figure_group",
        "Greco-Roman mythology",
        "CC BY-SA 4.0",
        "Scan the World via Wikimedia Commons",
        ("Complex multi-figure composition and repair-stress candidate.",),
        author_override="Scan the World",
    ),
    CuratedAsset(
        "statue-pieta-michelangelo",
        "File:Scan the World - Pietà (Michelangelo).stl",
        "Pietà",
        "Michelangelo's Pietà",
        "figure_group",
        "Christian; Italian Renaissance",
        "CC BY-SA 4.0",
        "Scan the World via Wikimedia Commons",
        ("Drapery-rich two-figure composition.",),
    ),
    CuratedAsset(
        "statue-thinker-rodin",
        "File:Scan the World - The Thinker (Auguste Rodin).stl",
        "The Thinker",
        "Auguste Rodin's The Thinker",
        "full_statue",
        "European modern sculpture",
        "CC BY-SA 4.0",
        "Scan the World via Wikimedia Commons",
        ("Dense organic seated figure.",),
    ),
    CuratedAsset(
        "statue-venus-de-milo",
        "File:Scan the World - Venus de Milo.stl",
        "Venus de Milo",
        "Marble statue of Aphrodite",
        "full_statue",
        "Ancient Greek religion",
        "CC BY-SA 4.0",
        "Scan the World via Wikimedia Commons",
        ("Fragmentary full-body classical statue.",),
    ),
    CuratedAsset(
        "statue-venus-willendorf",
        "File:Scan the World - Venus of Willendorf.stl",
        "Venus of Willendorf",
        "Upper Paleolithic female figurine",
        "figurine",
        "Upper Paleolithic European",
        "CC BY-SA 4.0",
        "Scan the World via Wikimedia Commons",
        ("Small artifact captured at comparatively high mesh density.",),
    ),
    CuratedAsset(
        "statue-water-buffalo-boy",
        "File:Wasserbüffel und Knabe - 3D model by noe-3d.at - Sketchfab.stl",
        "Water Buffalo and Boy",
        "Water buffalo with boy by Elisabeth Turolt",
        "figure_group",
        "Austrian modern public sculpture",
        "CC0",
        "noe-3d.at via Sketchfab and Wikimedia Commons",
        ("Animal-and-human outdoor sculpture scan.",),
    ),
    CuratedAsset(
        "statue-hizen-komainu",
        "File:肥前狛犬1（八龍社）.stl",
        "Hizen Komainu at Hachiryū Shrine",
        "Stone guardian lion-dog",
        "temple_guardian",
        "Shinto; Japanese",
        "CC BY-SA 4.0",
        "Independent photogrammetry via Wikimedia Commons",
        ("Large weathered photogrammetry mesh selected as a stress case.",),
    ),
    CuratedAsset(
        "statue-dainichi-nyorai-tower",
        "File:大日如来塔（十二神社）.stl",
        "Dainichi Nyorai Tower at Jūni Shrine",
        "Stone religious monument dedicated to Dainichi Nyorai",
        "temple_monument",
        "Esoteric Buddhism; Japanese",
        "CC BY 4.0",
        "Independent photogrammetry via Wikimedia Commons",
        ("Large inscribed stone monument scan.",),
    ),
    CuratedAsset(
        "statue-bato-kannon-shirane",
        "File:馬頭観音（横浜市旭区白根町）.stl",
        "Batō Kannon at Shirane",
        "Stone monument to horse-headed Kannon",
        "temple_monument",
        "Buddhist; Japanese",
        "CC BY 4.0",
        "Independent photogrammetry via Wikimedia Commons",
        ("Weathered religious stone scan with inscriptions.",),
    ),
    CuratedAsset(
        "statue-mick-odwyer",
        "File:Mick O'Dwyer - 3D model by Kerry3D @DH Age - Sketchfab.stl",
        "Mick O'Dwyer",
        "Public statue of Gaelic football player and manager Mick O'Dwyer",
        "full_statue",
        "Contemporary Irish commemorative sculpture",
        "CC0",
        "Kerry3D via Sketchfab and Wikimedia Commons",
        ("Modern clothed standing figure.",),
    ),
    CuratedAsset(
        "statue-heroic-head-pierre-de-wissant",
        "File:1917.722 Heroic Head of Pierre de Wissant - 3D model.stl",
        "Heroic Head of Pierre de Wissant",
        "Auguste Rodin portrait head",
        "head",
        "European modern sculpture",
        "CC0",
        "Museum scan via Wikimedia Commons",
        ("High-resolution expressive head study.",),
    ),
)


REJECTED_CANDIDATES = (
    {
        "title": "Cosmic Buddha full-resolution no-texture",
        "source_url": (
            "https://commons.wikimedia.org/wiki/"
            "File:Cosmic_buddha-full_resolution-no_texture_(Smithsonian_Institution).stl"
        ),
        "license": "CC0-1.0",
        "reason": (
            "Rejected before download: 2.88 GiB and roughly 62 million faces exceed "
            "this baseline corpus budget; the Smithsonian 150k derivative is retained."
        ),
    },
    {
        "title": "Gisant test",
        "source_url": "https://commons.wikimedia.org/wiki/File:Gisant_test.stl",
        "license": "CC-BY-SA-4.0",
        "reason": (
            "Rejected before download: source labels the asset only as a test and "
            "does not provide sufficient object provenance for the curated corpus."
        ),
    },
    {
        "title": "Generic Moai rendering",
        "source_url": "https://commons.wikimedia.org/wiki/File:Moai.stl",
        "license": "CC-BY-4.0",
        "reason": (
            "Rejected before download: generic rendering rather than a documented "
            "scan or identified heritage object."
        ),
    },
    {
        "title": "Open Heritage 3D general project downloads",
        "source_url": "https://openheritage3d.org/faq",
        "license": "Varies by project",
        "reason": (
            "Rejected as an acquisition route for this sprint: downloads require "
            "user identity fields and many projects prohibit commercial use."
        ),
    },
    {
        "title": "Sketchfab models without anonymous downloads",
        "source_url": "https://sketchfab.com/3d-models/categories/cultural-heritage-history",
        "license": "Varies by model",
        "reason": (
            "Rejected as an acquisition route unless mirrored by a public repository "
            "with model-level license evidence; direct downloads can require login."
        ),
    },
    {
        "title": "Paid marketplace statue meshes",
        "source_url": None,
        "license": "Paid or unclear redistribution terms",
        "reason": (
            "Rejected by policy: paid, private, or redistribution-restricted assets "
            "are outside this dataset."
        ),
    },
)


def _ensure_directories() -> None:
    for directory in (
        RAW_ROOT,
        PROCESSED_ROOT,
        METADATA_ROOT,
        THUMBNAIL_ROOT,
        MANIFEST_ROOT,
        LICENSE_ROOT,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _plain_text(value: str | None, *, limit: int = 2_000) -> str:
    if not value:
        return ""
    text = html.unescape(re.sub(r"<[^>]+>", " ", value))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _ext_value(metadata: dict[str, Any], key: str) -> str:
    item = metadata.get(key)
    if not isinstance(item, dict):
        return ""
    return str(item.get("value", ""))


def _extract_urls(value: str | None) -> list[str]:
    if not value:
        return []
    urls = re.findall(r"https?://[^\s\"'<>]+", html.unescape(value))
    cleaned = []
    for url in urls:
        normalized = url.rstrip(").,;")
        if normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _api_query(titles: list[str]) -> dict[str, dict[str, Any]]:
    payload = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "titles": "|".join(titles),
            "prop": "imageinfo|revisions",
            "iiprop": "url|size|mime|mediatype|sha1|extmetadata",
            "iiurlwidth": "512",
            "rvprop": "ids|timestamp",
            "rvslots": "main",
            "maxlag": "5",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        COMMONS_API_URL,
        data=payload,
        headers={"User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        document = json.load(response)

    if "error" in document:
        raise RuntimeError(f"Wikimedia API error: {document['error']}")

    pages = document.get("query", {}).get("pages", [])
    return {str(page["title"]): page for page in pages if "title" in page}


def _fetch_pages() -> dict[str, dict[str, Any]]:
    titles = [asset.commons_title for asset in CURATED_ASSETS]
    pages: dict[str, dict[str, Any]] = {}
    for offset in range(0, len(titles), 15):
        pages.update(_api_query(titles[offset : offset + 15]))
        if offset + 15 < len(titles):
            time.sleep(2)
    return pages


def _hash_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(
    url: str,
    destination: Path,
    *,
    expected_size: int | None = None,
) -> None:
    if destination.is_file():
        if expected_size is None or destination.stat().st_size == expected_size:
            return

    partial = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, 4):
        try:
            resume_at = partial.stat().st_size if partial.exists() else 0
            headers = {"User-Agent": USER_AGENT}
            if resume_at:
                headers["Range"] = f"bytes={resume_at}-"
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=180) as response:
                append = resume_at > 0 and getattr(response, "status", 200) == 206
                mode = "ab" if append else "wb"
                with partial.open(mode) as output:
                    while True:
                        chunk = response.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)

            if expected_size is not None and partial.stat().st_size != expected_size:
                raise RuntimeError(
                    f"size mismatch for {destination.name}: "
                    f"{partial.stat().st_size} != {expected_size}"
                )
            partial.replace(destination)
            return
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            if attempt == 3:
                raise RuntimeError(f"download failed for {url}: {exc}") from exc
            time.sleep(2**attempt)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _download_license_texts() -> None:
    for license_record in ALLOWED_LICENSES.values():
        _download(
            license_record["legal_text_url"],
            LICENSE_ROOT / license_record["local_file"],
        )


def _acquire_asset(
    asset: CuratedAsset,
    page: dict[str, Any],
    download_timestamp: str,
) -> dict[str, Any]:
    if page.get("missing"):
        raise RuntimeError(f"missing Wikimedia Commons page: {asset.commons_title}")

    image_info = page.get("imageinfo", [{}])[0]
    if image_info.get("mime") != "application/sla":
        raise RuntimeError(
            f"{asset.unique_id}: expected application/sla, got {image_info.get('mime')}"
        )

    extmetadata = image_info.get("extmetadata", {})
    source_license = _ext_value(extmetadata, "LicenseShortName")
    if source_license != asset.expected_license:
        raise RuntimeError(
            f"{asset.unique_id}: license drift "
            f"{source_license!r} != {asset.expected_license!r}"
        )
    if source_license not in ALLOWED_LICENSES:
        raise RuntimeError(f"{asset.unique_id}: license is not allowed")

    license_record = ALLOWED_LICENSES[source_license]
    original_filename = page["title"].removeprefix("File:")
    stored_filename = f"{asset.unique_id}.stl"
    raw_path = RAW_ROOT / stored_filename
    expected_size = int(image_info["size"])
    _download(image_info["url"], raw_path, expected_size=expected_size)

    source_sha1 = str(image_info.get("sha1", "")).lower()
    local_sha1 = _hash_file(raw_path, "sha1")
    if source_sha1 and source_sha1 != local_sha1:
        raise RuntimeError(
            f"{asset.unique_id}: Wikimedia SHA-1 mismatch "
            f"{local_sha1} != {source_sha1}"
        )

    thumbnail_url = image_info.get("thumburl")
    thumbnail_relative_path = None
    thumbnail_sha256 = None
    if thumbnail_url:
        thumbnail_path = THUMBNAIL_ROOT / f"{asset.unique_id}.png"
        _download(thumbnail_url, thumbnail_path)
        if thumbnail_path.stat().st_size == 0:
            raise RuntimeError(f"{asset.unique_id}: empty thumbnail")
        thumbnail_relative_path = thumbnail_path.relative_to(REPOSITORY_ROOT).as_posix()
        thumbnail_sha256 = _hash_file(thumbnail_path)

    revisions = page.get("revisions") or []
    revision = revisions[0] if revisions else {}
    revision_id = revision.get("revid")
    description_url = str(image_info["descriptionurl"])
    revision_url = (
        f"{description_url}?oldid={revision_id}" if revision_id else description_url
    )

    source_html = _ext_value(extmetadata, "Source")
    source_urls = _extract_urls(source_html)
    metadata = {
        "unique_id": asset.unique_id,
        "title": asset.title,
        "subject": asset.subject,
        "category": asset.category,
        "religious_cultural_classification": (
            asset.religious_cultural_classification
        ),
        "source_url": description_url,
        "source_revision_url": revision_url,
        "source_page_revision_id": revision_id,
        "source_page_revision_timestamp": revision.get("timestamp"),
        "download_url": image_info["url"],
        "download_date": download_timestamp[:10],
        "download_timestamp_utc": download_timestamp,
        "author": (
            _plain_text(_ext_value(extmetadata, "Artist"))
            or asset.author_override
            or "Not stated on source page"
        ),
        "credit": _plain_text(_ext_value(extmetadata, "Credit")),
        "original_repository": asset.original_repository,
        "upstream_source_urls": source_urls,
        "license": license_record["identifier"],
        "license_source_label": source_license,
        "license_url": license_record["url"],
        "license_document": (
            LICENSE_ROOT / license_record["local_file"]
        ).relative_to(REPOSITORY_ROOT).as_posix(),
        "file_format": "STL",
        "mime_type": image_info["mime"],
        "vertex_count": None,
        "triangle_count": None,
        "bounding_box": None,
        "checksum_sha256": _hash_file(raw_path),
        "source_checksum_sha1": source_sha1 or None,
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "stored_path": raw_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "file_size_bytes": raw_path.stat().st_size,
        "thumbnail_path": thumbnail_relative_path,
        "thumbnail_checksum_sha256": thumbnail_sha256,
        "source_description": _plain_text(
            _ext_value(extmetadata, "ImageDescription")
        ),
        "notes": list(asset.notes),
        "validation": {
            "status": "pending_blender_validation",
            "readable": None,
            "non_empty": raw_path.stat().st_size > 0,
            "reasonable_mesh": None,
            "obvious_corruption": None,
        },
    }
    _write_json(METADATA_ROOT / f"{asset.unique_id}.json", metadata)
    return metadata


def main() -> int:
    _ensure_directories()
    _download_license_texts()
    pages = _fetch_pages()
    download_timestamp = datetime.now(timezone.utc).isoformat()

    acquired = []
    failures = []
    for asset in CURATED_ASSETS:
        page = pages.get(asset.commons_title)
        if page is None:
            failures.append(
                {
                    "unique_id": asset.unique_id,
                    "title": asset.title,
                    "reason": "Wikimedia API did not return the requested page.",
                }
            )
            continue
        try:
            acquired.append(_acquire_asset(asset, page, download_timestamp))
            print(f"ACQUIRED {asset.unique_id}")
        except Exception as exc:
            failures.append(
                {
                    "unique_id": asset.unique_id,
                    "title": asset.title,
                    "reason": str(exc),
                }
            )
            print(f"FAILED {asset.unique_id}: {exc}")

    rejected_payload = {
        "dataset_version": DATASET_VERSION,
        "generated_at_utc": download_timestamp,
        "policy_rejections": list(REJECTED_CANDIDATES),
        "acquisition_failures": failures,
    }
    _write_json(METADATA_ROOT / "rejected_assets.json", rejected_payload)

    report = {
        "dataset_version": DATASET_VERSION,
        "generated_at_utc": download_timestamp,
        "requested_asset_count": len(CURATED_ASSETS),
        "downloaded_asset_count": len(acquired),
        "acquisition_failure_count": len(failures),
        "policy_rejection_count": len(REJECTED_CANDIDATES),
        "downloaded_bytes": sum(item["file_size_bytes"] for item in acquired),
        "assets": [
            {
                "unique_id": item["unique_id"],
                "stored_path": item["stored_path"],
                "checksum_sha256": item["checksum_sha256"],
            }
            for item in acquired
        ],
        "failures": failures,
    }
    _write_json(MANIFEST_ROOT / "acquisition_report.json", report)

    print(
        f"Acquired {len(acquired)}/{len(CURATED_ASSETS)} assets "
        f"({report['downloaded_bytes']} bytes)."
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
