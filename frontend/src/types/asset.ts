export type AssetArea = 'pending' | 'project' | 'library'
export type AssetType = 'image' | 'audio'
export type TargetArea = 'project' | 'library'

export interface Settings {
  owner_assets_path: string
  current_project: string
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
