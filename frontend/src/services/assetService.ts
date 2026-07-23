import { api } from '@/api/axios'
import type { ApiResponse } from '@/types'

// ── Types (old, kept for compatibility) ──
export interface AssetItem {
  id: string
  name: string
  count: number
  type: string
  accessLevel?: string
  lastUpdate: string
}
export interface AssetListResponse { assets: AssetItem[]; total: number; page: number; pages: number }
export interface AssetListParams { user_id?: string; page?: number; pageSize?: number }

// ── New Asset Types ──
export interface CharacterAsset {
  asset_id: string; name: string; role_type: string; gender: string
  age_range: string; appearance: string; clothing_style: string
  distinctive_features: string[]; reference_images: Record<string, string>
  expression_images: Record<string, string>; prompt_prefix: string
  usage_count: number; avg_quality_score: number; tags: string[]
  visibility: string; version: number
}
export interface SceneTemplate {
  template_id: string; name: string; category: string
  location_description: string; lighting_setup: Record<string, any>
  camera_setups: Array<Record<string, any>>; reference_images: string[]
  usage_count: number; tags: string[]; visibility: string; version: number
}
export interface ShotPreset {
  preset_id: string; name: string; shot_type: string; camera_angle: string
  camera_movement: string; focal_length: string; composition_rule: string
  depth_of_field: string; duration_range: string; description: string
  prompt_template: string; usage_count: number; avg_quality_score: number
  tags: string[]; visibility: string; version: number
}

export const assetService = {
  // ── Legacy (kept for compatibility) ──
  getPersonalAssets: async (params: AssetListParams = {}): Promise<AssetListResponse> => {
    const response = await api.get<AssetListResponse>('/v1/assets/personal', { params })
    return response.data
  },
  getCompanyAssets: async (params: AssetListParams = {}): Promise<AssetListResponse> => {
    const response = await api.get<AssetListResponse>('/v1/assets/company', { params })
    return response.data
  },

  // ── Characters ──
  createCharacter: async (data: Partial<CharacterAsset>): Promise<ApiResponse<any>> => {
    const res = await api.post('/v1/assets/characters', data); return res.data
  },
  listCharacters: async (params?: { role_type?: string; tags?: string; sort_by?: string; limit?: number }): Promise<ApiResponse<{ data: CharacterAsset[]; total: number }>> => {
    const res = await api.get('/v1/assets/characters', { params }); return res.data
  },
  getCharacter: async (assetId: string): Promise<ApiResponse<{ data: CharacterAsset }>> => {
    const res = await api.get(`/v1/assets/characters/${assetId}`); return res.data
  },
  updateCharacter: async (assetId: string, data: Partial<CharacterAsset>): Promise<ApiResponse<any>> => {
    const res = await api.put(`/v1/assets/characters/${assetId}`, data); return res.data
  },

  // ── Scenes ──
  createScene: async (data: Partial<SceneTemplate>): Promise<ApiResponse<any>> => {
    const res = await api.post('/v1/assets/scenes', data); return res.data
  },
  listScenes: async (params?: { category?: string; tags?: string; limit?: number }): Promise<ApiResponse<{ data: SceneTemplate[]; total: number }>> => {
    const res = await api.get('/v1/assets/scenes', { params }); return res.data
  },
  getScene: async (templateId: string): Promise<ApiResponse<{ data: SceneTemplate }>> => {
    const res = await api.get(`/v1/assets/scenes/${templateId}`); return res.data
  },

  // ── Shot Presets ──
  createShotPreset: async (data: Partial<ShotPreset>): Promise<ApiResponse<any>> => {
    const res = await api.post('/v1/assets/shot-presets', data); return res.data
  },
  listShotPresets: async (params?: { shot_type?: string; tags?: string; limit?: number }): Promise<ApiResponse<{ data: ShotPreset[]; total: number }>> => {
    const res = await api.get('/v1/assets/shot-presets', { params }); return res.data
  },
  getShotPreset: async (presetId: string): Promise<ApiResponse<{ data: ShotPreset }>> => {
    const res = await api.get(`/v1/assets/shot-presets/${presetId}`); return res.data
  },

  // ── Context Builder ──
  buildContext: async (data: { character_ids?: string[]; scene_template_id?: string; shot_preset_ids?: string[] }): Promise<ApiResponse<{ data: Record<string, any> }>> => {
    const res = await api.post('/v1/assets/build-context', data); return res.data
  },
}
