import axios from 'axios'
import type { Asset, AssetArea, AssetMetaPayload, AssetType, MoveAssetPayload, Settings } from '@/types/asset'

export const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
})

export async function getSettings() {
  const response = await api.get<Settings>('/settings')
  return response.data
}

export async function saveSettings(settings: Settings) {
  const response = await api.post<Settings>('/settings', settings)
  return response.data
}

export async function initAssets() {
  const response = await api.post<{ ok: boolean }>('/init')
  return response.data
}

export async function getProjects() {
  const response = await api.get<string[]>('/projects')
  return response.data
}

export async function createProject(name: string) {
  const response = await api.post<Settings>('/projects', { name })
  return response.data
}

export async function getCategories(area: AssetArea, type?: AssetType) {
  const response = await api.get<string[]>('/categories', { params: { area, type } })
  return response.data
}

export async function createCategory(area: 'project' | 'library', type: AssetType, name: string) {
  const response = await api.post<{ ok: boolean }>('/categories', { area, type, name })
  return response.data
}

export async function scanAssets(area: AssetArea | 'all' = 'all') {
  const response = await api.post<Record<string, Asset[]> | Asset[]>('/scan', null, { params: { area } })
  return response.data
}

export async function getAssets(params: {
  area?: AssetArea
  type?: AssetType
  category?: string
  keyword?: string
}) {
  const response = await api.get<Asset[]>('/assets', { params })
  return response.data
}

export async function updateAssetMeta(payload: AssetMetaPayload) {
  const response = await api.post<Asset>('/assets/meta', payload)
  return response.data
}

export async function moveAsset(payload: MoveAssetPayload) {
  const response = await api.post<Asset>('/assets/move', payload)
  return response.data
}

export async function openAssetFolder(assetId: string) {
  const response = await api.post<{ ok: boolean }>(`/assets/open-folder/${assetId}`)
  return response.data
}

export async function renameAsset(assetId: string, newName: string) {
  const response = await api.post<Asset>('/assets/rename', { asset_id: assetId, new_name: newName })
  return response.data
}

export async function deleteAsset(assetId: string) {
  const response = await api.post<Asset>('/assets/delete', { asset_id: assetId })
  return response.data
}

export async function permanentDeleteAsset(assetId: string) {
  const response = await api.post<{ ok: boolean }>('/assets/permanent-delete', { asset_id: assetId })
  return response.data
}

export async function getAudioInfo(assetId: string) {
  const response = await api.get<{ duration: number; sampleRate: number; channels: number }>(`/assets/audio-info/${assetId}`)
  return response.data
}

export function assetFileUrl(assetId: string) {
  return `${api.defaults.baseURL}/assets/file/${assetId}`
}
