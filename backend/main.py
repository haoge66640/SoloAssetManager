from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .models import (
    AssetQuery,
    AssetUpdateRequest,
    CategoryCreateRequest,
    CategoryPathRequest,
    DeleteAssetRequest,
    DeleteCategoryRequest,
    FormatAssetRequest,
    MoveAssetRequest,
    ProjectCreateRequest,
    RenameAssetRequest,
    Settings,
    SyncCategoryRequest,
    TagCreateRequest,
    TagDeleteRequest,
    WaveformBatchRequest,
)
from .storage import (
    audio_info,
    compute_waveform,
    copy_asset_to_target,
    create_category,
    create_project,
    delete_category_from_disk,
    file_path_by_id,
    format_with_ffmpeg,
    get_category_paths,
    get_settings,
    import_from_path,
    init_owner_assets,
    list_categories,
    list_projects,
    list_tags,
    add_tag,
    remove_tag,
    move_from_pending,
    move_to_pending,
    open_folder,
    permanent_delete_asset,
    query_assets,
    rename_asset,
    save_settings,
    scan_all,
    scan_area,
    scan_pending,
    set_category_target_path,
    sync_category,
    update_asset_meta,
)

app = FastAPI(title="Solo Asset Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/settings")
def read_settings() -> Settings:
    return get_settings()


@app.post("/settings")
def write_settings(settings: Settings) -> Settings:
    return save_settings(settings)


@app.post("/init")
def init_assets() -> dict:
    return init_owner_assets()


@app.get("/projects")
def read_projects() -> list[str]:
    return list_projects()


@app.post("/projects")
def add_project(request: ProjectCreateRequest) -> Settings:
    return create_project(request.name)


@app.get("/categories")
def read_categories(area: str, type: str = "") -> list[str]:
    return list_categories(area, type)


@app.post("/categories")
def add_category(request: CategoryCreateRequest) -> dict:
    return create_category(request.area, request.type, request.name)


@app.get("/categories/paths")
def read_category_paths(area: str):
    """Get category target paths for an area: {type: {category: target_path}}"""
    return get_category_paths(area)


@app.post("/categories/path")
def update_category_path(request: CategoryPathRequest):
    set_category_target_path(request.area, request.type, request.name, request.target_path)
    return {"ok": True}


@app.delete("/categories")
def remove_category(request: DeleteCategoryRequest):
    return delete_category_from_disk(request.area, request.type, request.name)


@app.post("/scan")
def scan(area: str = "all"):
    if area == "pending":
        return scan_pending()
    if area in ("project", "library"):
        return scan_area(area)
    return scan_all()


@app.get("/assets")
def read_assets(area: str | None = None, type: str | None = None, category: str = "", keyword: str = ""):
    query = AssetQuery(area=area, type=type, category=category, keyword=keyword)
    return query_assets(query.area, query.type, query.category, query.keyword)


@app.post("/assets/meta")
def update_meta(request: AssetUpdateRequest):
    return update_asset_meta(
        request.asset_id,
        request.source_type,
        request.source_url,
        request.tags,
        request.note,
    )


@app.post("/assets/move")
def move_asset(request: MoveAssetRequest):
    return move_from_pending(
        request.asset_id,
        request.target_area,
        request.category,
        request.source_type,
        request.source_url,
        request.tags,
        request.note,
    )


@app.get("/assets/file/{asset_id}")
def read_asset_file(asset_id: str):
    path: Path = file_path_by_id(asset_id)
    return FileResponse(path)


@app.get("/assets/audio-info/{asset_id}")
def read_audio_info(asset_id: str):
    return audio_info(asset_id)


@app.get("/assets/waveform/{asset_id}")
def read_waveform(asset_id: str, count: int = 600):
    return compute_waveform(asset_id, count)


@app.post("/assets/waveform/batch")
def read_waveform_batch(request: WaveformBatchRequest):
    """批量获取多个音频的波形峰值，把一页 N 个请求合并为 1 个。"""
    waveforms: dict[str, list[float]] = {}
    for asset_id in request.asset_ids:
        try:
            waveforms[asset_id] = compute_waveform(asset_id, request.count)["peaks"]
        except Exception:
            waveforms[asset_id] = []
    return {"waveforms": waveforms}


@app.post("/assets/rename")
def rename_asset_endpoint(request: RenameAssetRequest):
    return rename_asset(request.asset_id, request.new_name)


@app.post("/assets/delete")
def delete_asset_endpoint(request: DeleteAssetRequest):
    return move_to_pending(request.asset_id)


@app.post("/assets/permanent-delete")
def permanent_delete_asset_endpoint(request: DeleteAssetRequest):
    return permanent_delete_asset(request.asset_id)


@app.post("/assets/format")
def format_asset_endpoint(request: FormatAssetRequest):
    return format_with_ffmpeg(request.asset_id)


@app.post("/assets/open-folder/{asset_id}")
def open_asset_folder(asset_id: str):
    return open_folder(asset_id)


@app.post("/assets/copy-to-target/{asset_id}")
def copy_to_target(asset_id: str):
    return copy_asset_to_target(asset_id)


@app.post("/categories/sync")
def sync(request: SyncCategoryRequest):
    return sync_category(request.area, request.type, request.category)


@app.post("/assets/import")
def import_assets():
    return import_from_path()


@app.get("/tags")
def read_tags():
    return list_tags()


@app.post("/tags")
def create_tag(request: TagCreateRequest):
    return add_tag(request.category, request.name)


@app.delete("/tags")
def delete_tag(request: TagDeleteRequest):
    return remove_tag(request.category, request.name)
