from typing import Literal

from pydantic import BaseModel


AssetArea = Literal["pending", "project", "library"]
AssetType = Literal["image", "audio"]
TargetArea = Literal["project", "library"]


class Settings(BaseModel):
    owner_assets_path: str = ""
    current_project: str = ""


class Asset(BaseModel):
    id: str
    area: AssetArea
    type: AssetType
    format: str
    name: str
    path: str
    relative_path: str
    category: str = ""
    size: int
    modified_at: str
    source_type: str = ""
    source_url: str = ""
    tags: list[str] = []
    note: str = ""


class ProjectCreateRequest(BaseModel):
    name: str


class CategoryCreateRequest(BaseModel):
    area: TargetArea
    type: AssetType
    name: str


class AssetUpdateRequest(BaseModel):
    asset_id: str
    source_type: str = ""
    source_url: str = ""
    tags: list[str] = []
    note: str = ""


class MoveAssetRequest(BaseModel):
    asset_id: str
    target_area: TargetArea
    category: str
    source_type: str = ""
    source_url: str = ""
    tags: list[str] = []
    note: str = ""


class RenameAssetRequest(BaseModel):
    asset_id: str
    new_name: str


class DeleteAssetRequest(BaseModel):
    asset_id: str


class AssetQuery(BaseModel):
    area: AssetArea | None = None
    type: AssetType | None = None
    category: str = ""
    keyword: str = ""
