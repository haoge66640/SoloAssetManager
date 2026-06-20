import hashlib
import json
import os
import random
import re
import shutil
import struct
import subprocess
from datetime import datetime
from pathlib import Path

from .models import Asset, AssetType, Settings


DATA_DIR = Path(__file__).parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
INDEX_FILES = {
    "pending": DATA_DIR / "pending_assets.json",
    "project": DATA_DIR / "project_assets.json",
    "library": DATA_DIR / "library_assets.json",
}
TAGS_FILE = DATA_DIR / "tags.json"
SOURCES_FILE = DATA_DIR / "sources.json"
HISTORY_FILE = DATA_DIR / "history.json"
CATEGORY_PATHS_FILE = DATA_DIR / "category_paths.json"

TYPE_DIRS = {
    "image": "图片",
    "audio": "音频",
}
SUPPORTED_EXTENSIONS = {
    ".png": "image",
    ".svg": "image",
    ".ogg": "audio",
    ".wav": "audio",
}


def ensure_data_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not SETTINGS_FILE.exists():
        write_json(SETTINGS_FILE, Settings().model_dump())
    for file in INDEX_FILES.values():
        if not file.exists():
            write_json(file, [])
    if not TAGS_FILE.exists():
        write_json(TAGS_FILE, [])
    if not SOURCES_FILE.exists():
        write_json(SOURCES_FILE, [])
    if not HISTORY_FILE.exists():
        write_json(HISTORY_FILE, [])
    if not CATEGORY_PATHS_FILE.exists():
        write_json(CATEGORY_PATHS_FILE, {})


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_settings() -> Settings:
    ensure_data_files()
    return Settings(**read_json(SETTINGS_FILE, {}))


def save_settings(settings: Settings) -> Settings:
    ensure_data_files()
    write_json(SETTINGS_FILE, settings.model_dump())
    return settings


def owner_root() -> Path:
    return Path(get_settings().owner_assets_path)


def project_root() -> Path:
    return owner_root() / "Project"


def pending_root() -> Path:
    return owner_root() / "待选池"


def library_root() -> Path:
    return owner_root() / "仓库"


def current_project_root() -> Path:
    settings = get_settings()
    return project_root() / settings.current_project


def init_owner_assets() -> dict:
    settings = get_settings()
    root = Path(settings.owner_assets_path)
    (root / "Project").mkdir(parents=True, exist_ok=True)
    (root / "待选池").mkdir(parents=True, exist_ok=True)
    for type_dir in TYPE_DIRS.values():
        (root / "仓库" / type_dir).mkdir(parents=True, exist_ok=True)
    if settings.current_project:
        ensure_project(settings.current_project)
    return {"ok": True}


def ensure_project(name: str) -> None:
    for type_dir in TYPE_DIRS.values():
        (project_root() / name / type_dir).mkdir(parents=True, exist_ok=True)


def create_project(name: str) -> Settings:
    ensure_project(name)
    settings = get_settings()
    if not settings.current_project:
        settings.current_project = name
        save_settings(settings)
    return settings


def list_projects() -> list[str]:
    root = project_root()
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def type_dir(asset_type: AssetType) -> str:
    return TYPE_DIRS[asset_type]


def list_categories(area: str, asset_type: AssetType) -> list[str]:
    if area == "pending":
        root = pending_root()
        if not root.exists():
            return []
        return sorted(path.name for path in root.iterdir() if path.is_dir())

    base = current_project_root() if area == "project" else library_root()
    root = base / type_dir(asset_type)
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def create_category(area: str, asset_type: AssetType, name: str) -> dict:
    base = current_project_root() if area == "project" else library_root()
    (base / type_dir(asset_type) / name).mkdir(parents=True, exist_ok=True)
    init_category_paths(area, asset_type, name)
    return {"ok": True}


def delete_category_from_disk(area: str, asset_type: AssetType, name: str) -> dict:
    base = current_project_root() if area == "project" else library_root()
    target = base / type_dir(asset_type) / name
    if target.exists() and target.is_dir():
        shutil.rmtree(target)
    # Clean up saved target path
    paths = get_category_paths_raw()
    (paths.setdefault(area, {}).setdefault(asset_type, {})).pop(name, None)
    write_json(CATEGORY_PATHS_FILE, paths)
    return {"ok": True}


def init_category_paths(area: str, asset_type: AssetType, name: str) -> None:
    """Ensure a category entry exists in paths storage, without overwriting."""
    paths = get_category_paths_raw()
    area_data = paths.setdefault(area, {})
    type_data = area_data.setdefault(asset_type, {})
    if name not in type_data:
        type_data[name] = ""
    write_json(CATEGORY_PATHS_FILE, paths)


def get_category_paths_raw() -> dict:
    ensure_data_files()
    return read_json(CATEGORY_PATHS_FILE, {})


def get_category_paths(area: str) -> dict:
    """Returns {type: {category: target_path}} for the given area."""
    paths = get_category_paths_raw()
    return paths.get(area, {})


def set_category_target_path(area: str, asset_type: AssetType, name: str, target_path: str) -> None:
    paths = get_category_paths_raw()
    area_data = paths.setdefault(area, {})
    type_data = area_data.setdefault(asset_type, {})
    type_data[name] = target_path
    write_json(CATEGORY_PATHS_FILE, paths)


def asset_id(path: Path) -> str:
    normalized = str(path.resolve()).replace("\\", "/").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def normalized(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def datetime_text(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def index_file(area: str) -> Path:
    return INDEX_FILES[area]


def load_assets(area: str) -> list[Asset]:
    ensure_data_files()
    return [Asset(**item) for item in read_json(index_file(area), [])]


def save_assets(area: str, assets: list[Asset]) -> None:
    write_json(index_file(area), [asset.model_dump() for asset in assets])


def metadata_by_path(area: str) -> dict[str, Asset]:
    return {asset.path: asset for asset in load_assets(area)}


def build_asset(path: Path, area: str, base: Path, old: Asset | None = None) -> Asset:
    suffix = path.suffix.lower()
    asset_type = SUPPORTED_EXTENSIONS[suffix]
    relative_path = path.relative_to(owner_root()).as_posix()
    category = ""
    if area == "pending":
        parent = path.parent
        if parent != base:
            category = parent.relative_to(base).parts[0]
    else:
        type_root = base / TYPE_DIRS[asset_type]
        parent = path.parent
        if parent != type_root:
            category = parent.relative_to(type_root).parts[0]
    return Asset(
        id=asset_id(path),
        area=area,
        type=asset_type,
        format=suffix[1:],
        name=path.name,
        path=normalized(path),
        relative_path=relative_path,
        category=category,
        size=path.stat().st_size,
        modified_at=datetime_text(path.stat().st_mtime),
        source_type=old.source_type if old else "",
        source_url=old.source_url if old else "",
        tags=old.tags if old else [],
        note=old.note if old else "",
    )


def scan_pending() -> list[Asset]:
    root = pending_root()
    old_assets = metadata_by_path("pending")
    assets = []
    if root.exists():
        for path in sorted(root.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                assets.append(build_asset(path, "pending", root, old_assets.get(normalized(path))))
            if path.is_dir():
                for child in sorted(path.iterdir()):
                    if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                        assets.append(build_asset(child, "pending", root, old_assets.get(normalized(child))))
    save_assets("pending", assets)
    return assets


def scan_area(area: str) -> list[Asset]:
    base = current_project_root() if area == "project" else library_root()
    old_assets = metadata_by_path(area)
    assets = []
    for type_name in TYPE_DIRS.values():
        root = base / type_name
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    assets.append(build_asset(path, area, base, old_assets.get(normalized(path))))
    save_assets(area, assets)
    return assets


def scan_all() -> dict[str, list[Asset]]:
    return {
        "pending": scan_pending(),
        "project": scan_area("project"),
        "library": scan_area("library"),
    }


def list_all_assets() -> list[Asset]:
    assets: list[Asset] = []
    for area in INDEX_FILES:
        assets.extend(load_assets(area))
    return assets


def query_assets(area: str | None, asset_type: str | None, category: str, keyword: str) -> list[Asset]:
    assets = list_all_assets()
    if area:
        assets = [asset for asset in assets if asset.area == area]
    if asset_type:
        assets = [asset for asset in assets if asset.type == asset_type]
    if category:
        assets = [asset for asset in assets if asset.category == category]
    if keyword:
        text = keyword.lower()
        assets = [
            asset
            for asset in assets
            if text in asset.name.lower()
            or text in asset.source_url.lower()
            or text in asset.note.lower()
            or any(text in tag.lower() for tag in asset.tags)
        ]
    return assets


def find_asset(asset_id_value: str) -> tuple[str, Asset]:
    for area in INDEX_FILES:
        for asset in load_assets(area):
            if asset.id == asset_id_value:
                return area, asset
    raise FileNotFoundError(asset_id_value)


def update_asset_meta(asset_id_value: str, source_type: str, source_url: str, tags: list[str], note: str) -> Asset:
    area, target = find_asset(asset_id_value)
    assets = load_assets(area)
    for index, asset in enumerate(assets):
        if asset.id == asset_id_value:
            asset.source_type = source_type
            asset.source_url = source_url
            asset.tags = tags
            asset.note = note
            assets[index] = asset
            save_assets(area, assets)
            return asset
    raise FileNotFoundError(asset_id_value)


def next_random_name(source: Path, target_dir: Path | None = None) -> str:
    ext = source.suffix.lower()
    stem = source.stem
    # If filename already starts with 6 digits, reuse them
    prefix_match = re.match(r"^\d{6}", stem)
    prefix = prefix_match.group() if prefix_match else f"{random.randint(100000, 999999)}"
    name = f"{prefix}{ext}"
    # Handle collision: regenerate if name exists in target directory
    attempts = 0
    while target_dir and (target_dir / name).exists() and attempts < 100:
        prefix = f"{random.randint(100000, 999999)}"
        name = f"{prefix}{ext}"
        attempts += 1
    return name


def move_from_pending(asset_id_value: str, target_area: str, category: str, source_type: str, source_url: str, tags: list[str], note: str) -> Asset:
    area, asset = find_asset(asset_id_value)
    if area != "pending":
        raise ValueError("Only pending assets can be moved.")
    source = Path(asset.path)
    base = current_project_root() if target_area == "project" else library_root()
    target_dir = base / TYPE_DIRS[asset.type] / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / next_random_name(source, target_dir)
    shutil.move(str(source), str(target_path))
    moved = build_asset(target_path, target_area, base)
    moved.source_type = source_type
    moved.source_url = source_url
    moved.tags = tags
    moved.note = note
    save_assets("pending", [item for item in load_assets("pending") if item.id != asset_id_value])
    target_assets = [item for item in load_assets(target_area) if item.id != moved.id]
    target_assets.append(moved)
    save_assets(target_area, sorted(target_assets, key=lambda item: item.path))
    append_history({"action": "move", "from": asset.path, "to": moved.path})
    return moved


def move_to_pending(asset_id_value: str) -> Asset:
    area, asset = find_asset(asset_id_value)
    if area == "pending":
        raise ValueError("Asset is already in pending.")
    source = Path(asset.path)
    target_path = pending_root() / next_random_name(source, pending_root())
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target_path))
    moved = build_asset(target_path, "pending", pending_root(), asset)
    save_assets(area, [item for item in load_assets(area) if item.id != asset_id_value and item.id != moved.id])
    pending_assets = [item for item in load_assets("pending") if item.id != moved.id]
    pending_assets.append(moved)
    save_assets("pending", sorted(pending_assets, key=lambda item: item.path))
    append_history({"action": "delete", "from": asset.path, "to": moved.path})
    return moved


def append_history(item: dict) -> None:
    history = read_json(HISTORY_FILE, [])
    item["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history.append(item)
    write_json(HISTORY_FILE, history)


def file_path_by_id(asset_id_value: str) -> Path:
    _, asset = find_asset(asset_id_value)
    return Path(asset.path)


def audio_info(asset_id_value: str) -> dict:
    path = file_path_by_id(asset_id_value)
    output = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate,channels:format=duration",
            "-of",
            "json",
            str(path),
        ],
        encoding="utf-8",
    )
    data = json.loads(output)
    stream = (data.get("streams") or [{}])[0]
    audio_format = data.get("format") or {}
    return {
        "duration": float(audio_format.get("duration") or 0),
        "sampleRate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
    }


_waveform_cache: dict[str, tuple[list[int], int]] = {}
_WAVEFORM_CACHE_MAX = 100


def _get_cached_samples(asset_id_value: str) -> list[int]:
    """Return cached raw PCM samples for an asset, or decode and cache them."""
    if asset_id_value in _waveform_cache:
        return _waveform_cache[asset_id_value][0]
    path = file_path_by_id(asset_id_value)
    result = subprocess.run(
        ["ffmpeg", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "8000", "-y", "pipe:1"],
        capture_output=True, check=True,
    )
    raw = result.stdout
    sample_count = len(raw) // 2
    samples: list[int] = list(struct.unpack(f"<{sample_count}h", raw[:sample_count * 2]))
    # Evict oldest if cache is full
    if len(_waveform_cache) >= _WAVEFORM_CACHE_MAX:
        oldest = next(iter(_waveform_cache))
        del _waveform_cache[oldest]
    _waveform_cache[asset_id_value] = (samples, id(samples))
    return samples


def compute_waveform(asset_id_value: str, count: int = 600) -> dict:
    count = max(20, min(2000, count))
    samples = _get_cached_samples(asset_id_value)
    samples_per_bar = max(1, len(samples) // count)
    peaks = []
    for i in range(count):
        start = i * samples_per_bar
        end = len(samples) if i == count - 1 else start + samples_per_bar
        segment = samples[start:end]
        peak = max(abs(s) for s in segment) / 32768.0 if segment else 0
        peaks.append(round(peak, 4))
    return {"peaks": peaks}


def rename_asset(asset_id_value: str, new_name: str) -> Asset:
    if not new_name:
        raise ValueError("New name cannot be empty")
    area, asset = find_asset(asset_id_value)
    source = Path(asset.path)
    new_path = source.parent / new_name
    if new_path.exists():
        raise FileExistsError(f"File {new_path} already exists")
    source.rename(new_path)
    base = (
        pending_root()
        if area == "pending"
        else current_project_root() if area == "project" else library_root()
    )
    renamed = build_asset(new_path, area, base, asset)
    assets = load_assets(area)
    assets = [a for a in assets if a.id != asset_id_value]
    assets = [a for a in assets if a.id != renamed.id]
    assets.append(renamed)
    save_assets(area, sorted(assets, key=lambda a: a.path))
    append_history({"action": "rename", "from": asset.path, "to": renamed.path})
    return renamed


def open_folder(asset_id_value: str) -> dict:
    path = file_path_by_id(asset_id_value)
    os.startfile(path.parent)
    return {"ok": True}


def format_with_ffmpeg(asset_id_value: str) -> Asset:
    area, asset = find_asset(asset_id_value)
    source = Path(asset.path)
    output = source.parent / f"{source.stem}.wav"
    temp_output = source.parent / f"._fmt_{source.name}.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-ar", "44100", "-ac", "1", str(temp_output)],
        check=True, capture_output=True,
    )
    source.unlink(missing_ok=True)
    output.unlink(missing_ok=True)
    temp_output.rename(output)
    base = (
        pending_root()
        if area == "pending"
        else current_project_root() if area == "project" else library_root()
    )
    formatted = build_asset(output, area, base, asset)
    assets = load_assets(area)
    assets = [a for a in assets if a.id != asset_id_value and a.id != formatted.id]
    assets.append(formatted)
    save_assets(area, sorted(assets, key=lambda a: a.path))
    append_history({"action": "format", "from": asset.path, "to": formatted.path})
    return formatted


def permanent_delete_asset(asset_id_value: str) -> dict:
    _, asset = find_asset(asset_id_value)
    path = Path(asset.path)
    if path.exists():
        path.unlink()
    for area_key in INDEX_FILES:
        save_assets(area_key, [item for item in load_assets(area_key) if item.id != asset_id_value])
    append_history({"action": "permanent_delete", "from": asset.path})
    return {"ok": True}


def copy_asset_to_target(asset_id_value: str) -> dict:
    area, asset = find_asset(asset_id_value)
    if area == "pending":
        raise ValueError("Cannot copy from pending area")
    if not asset.category:
        raise ValueError("Asset has no category")
    paths = get_category_paths_raw()
    target_raw = (paths.get(area, {}).get(asset.type, {})).get(asset.category, "")
    if not target_raw:
        raise ValueError(f"No target path configured for category '{asset.category}'")
    target_dir = Path(target_raw)
    target_dir.mkdir(parents=True, exist_ok=True)
    source = Path(asset.path)
    dest = target_dir / next_random_name(source, target_dir)
    shutil.copy2(str(source), str(dest))
    append_history({"action": "copy_to_target", "from": asset.path, "to": str(dest)})
    return {"ok": True, "target": str(dest)}
