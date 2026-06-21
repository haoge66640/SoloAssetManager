from typing import Literal

from pydantic import BaseModel


AssetArea = Literal["pending", "project", "library"]
AssetType = Literal["image", "audio"]
TargetArea = Literal["project", "library"]
TagCategory = Literal["general", "audio", "image"]


class Settings(BaseModel):
    owner_assets_path: str = ""
    current_project: str = ""
    import_path: str = ""


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
    # 音频元数据（扫描时预计算，避免每次请求启动 ffprobe）
    duration: float = 0.0
    sample_rate: int = 0
    channels: int = 0


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


class FormatAssetRequest(BaseModel):
    asset_id: str


class AssetQuery(BaseModel):
    area: AssetArea | None = None
    type: AssetType | None = None
    category: str = ""
    keyword: str = ""


class WaveformBatchRequest(BaseModel):
    asset_ids: list[str]
    count: int = 150


class CategoryPathRequest(BaseModel):
    area: TargetArea
    type: AssetType
    name: str
    target_path: str = ""


class DeleteCategoryRequest(BaseModel):
    area: TargetArea
    type: AssetType
    name: str


class SyncCategoryRequest(BaseModel):
    area: TargetArea
    type: AssetType
    category: str


class TagItem(BaseModel):
    category: TagCategory
    name: str


class Tag(BaseModel):
    category: TagCategory
    name: str
    count: int = 0


class TagCreateRequest(BaseModel):
    category: TagCategory
    name: str


class TagDeleteRequest(BaseModel):
    category: TagCategory
    name: str
