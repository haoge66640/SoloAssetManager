from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .models import (
    AssetQuery,
    AssetUpdateRequest,
    CategoryCreateRequest,
    DeleteAssetRequest,
    MoveAssetRequest,
    ProjectCreateRequest,
    RenameAssetRequest,
    Settings,
)
from .storage import (
    audio_info,
    create_category,
    create_project,
    file_path_by_id,
    get_settings,
    init_owner_assets,
    list_categories,
    list_projects,
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


@app.post("/assets/rename")
def rename_asset_endpoint(request: RenameAssetRequest):
    return rename_asset(request.asset_id, request.new_name)


@app.post("/assets/delete")
def delete_asset_endpoint(request: DeleteAssetRequest):
    return move_to_pending(request.asset_id)


@app.post("/assets/permanent-delete")
def permanent_delete_asset_endpoint(request: DeleteAssetRequest):
    return permanent_delete_asset(request.asset_id)


@app.post("/assets/open-folder/{asset_id}")
def open_asset_folder(asset_id: str):
    return open_folder(asset_id)
