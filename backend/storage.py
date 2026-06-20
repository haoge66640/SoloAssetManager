import hashlib
import json
import os
import re
import shutil
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
    return {"ok": True}


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


def strip_number_suffix(stem: str) -> str:
    return re.sub(r"_\d+$", "", stem)


def next_numbered_name(source: Path) -> str:
    base_stem = strip_number_suffix(source.stem)
    ext = source.suffix.lower()
    pattern = re.compile(rf"^{re.escape(base_stem)}_(\d+){re.escape(ext)}$", re.IGNORECASE)
    max_number = 0
    for path in owner_root().rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            match = pattern.match(path.name)
            if match:
                max_number = max(max_number, int(match.group(1)))
    return f"{base_stem}_{max_number + 1}{ext}"


def move_from_pending(asset_id_value: str, target_area: str, category: str, source_type: str, source_url: str, tags: list[str], note: str) -> Asset:
    area, asset = find_asset(asset_id_value)
    if area != "pending":
        raise ValueError("Only pending assets can be moved.")
    source = Path(asset.path)
    base = current_project_root() if target_area == "project" else library_root()
    target_dir = base / TYPE_DIRS[asset.type] / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / next_numbered_name(source)
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
