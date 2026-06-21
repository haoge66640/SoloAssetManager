export type AssetArea = 'pending' | 'project' | 'library'
export type AssetType = 'image' | 'audio'
export type TargetArea = 'project' | 'library'
export type TagCategory = 'general' | 'audio' | 'image'

export interface Settings {
  owner_assets_path: string
  current_project: string
  import_path: string
}

export interface Asset {
  id: string
  area: AssetArea
  type: AssetType
  format: string
  name: string
  path: string
  relative_path: string
  category: string
  size: number
  modified_at: string
  source_type: string
  source_url: string
  tags: string[]
  note: string
  // 音频元数据（后端扫描时预计算）
  duration: number
  sample_rate: number
  channels: number
}

export interface AssetMetaPayload {
  asset_id: string
  source_type: string
  source_url: string
  tags: string[]
  note: string
}

export interface MoveAssetPayload extends AssetMetaPayload {
  target_area: TargetArea
  category: string
}

export interface Tag {
  category: TagCategory
  name: string
  count: number
}
