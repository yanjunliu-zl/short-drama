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

// ── Go backend response types ──
export interface GoCharacter {
  id: number
  name: string
  description: string
  age: number
  gender: string
  role: string
  createdAt: string
  updatedAt: string
}

export interface GoScene {
  id: number
  title: string
  description: string
  location: string
  timeOfDay: string
  characters: string[]
  content: string
  order: number
  createdAt: string
  updatedAt: string
}

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

/** Map Go backend Character to frontend CharacterAsset for display */
function goCharToAsset(c: GoCharacter): CharacterAsset {
  return {
    asset_id: String(c.id),
    name: c.name,
    role_type: c.role || '配角',
    gender: c.gender || '',
    age_range: c.age ? String(c.age) : '',
    appearance: c.description || '',
    clothing_style: '',
    distinctive_features: [],
    reference_images: {},
    expression_images: {},
    prompt_prefix: '',
    usage_count: 0,
    avg_quality_score: 0,
    tags: c.role ? [c.role] : [],
    visibility: 'private',
    version: 1,
  }
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
  /** Create a character via Go backend. Accepts both AssetLibrary form format and simple Scene-page format. */
  createCharacter: async (data: Partial<CharacterAsset> | {
    name: string
    description?: string
    age?: number
    gender?: string
    role?: string
  }): Promise<ApiResponse<any>> => {
    // Map from either rich (CharacterAsset) or simple format to Go backend fields
    const d = data as any
    const payload = {
      name: d.name || '',
      description: d.description || d.appearance || '',
      age: typeof d.age === 'number' ? d.age : (d.age_range ? ({ '少年': 16, '青年': 25, '中年': 40, '老年': 65 } as Record<string, number>)[d.age_range] || 25 : 25),
      gender: d.gender || '其他',
      role: d.role || d.role_type || '配角',
    }
    const res = await api.post('/v1/characters', payload)
    return res.data
  },

  /** Update a character via Go backend */
  updateCharacter: async (id: number | string, data: {
    name?: string
    description?: string
    age?: number
    gender?: string
    role?: string
  }): Promise<ApiResponse<any>> => {
    const res = await api.put(`/v1/characters/${id}`, data)
    return res.data
  },

  /** List characters from Go backend, returns as CharacterAsset[] for UI compatibility */
  listCharacters: async (params?: {
    role_type?: string; tags?: string; sort_by?: string; limit?: number
  }): Promise<{ data: CharacterAsset[]; total: number }> => {
    const res = await api.get<{ characters: GoCharacter[]; total: number; page: number; pages: number }>(
      '/v1/characters',
      { params: { page: 1, pageSize: params?.limit || 50 } }
    )
    const body = res.data
    if (body && body.characters) {
      return { data: body.characters.map(goCharToAsset), total: body.total }
    }
    return { data: [], total: 0 }
  },

  getCharacter: async (assetId: string): Promise<ApiResponse<{ data: CharacterAsset }>> => {
    const res = await api.get(`/v1/characters/${assetId}`)
    const c: GoCharacter = res.data
    return { success: true, data: { data: goCharToAsset(c) }, code: 200, message: 'ok' } as any
  },

  // ── Scenes ──
  /** Create a scene via Go backend. Accepts both AssetLibrary form format and simple format. */
  createScene: async (data: Partial<SceneTemplate> | {
    title: string
    description?: string
    location?: string
    timeOfDay?: string
    characters?: string[]
    content?: string
    order?: number
  }): Promise<ApiResponse<any>> => {
    const d = data as any
    const payload = {
      title: d.title || d.name || '',
      description: d.description || d.location_description || '',
      location: d.location || d.category || '',
      timeOfDay: d.timeOfDay || d.lighting_style || '',
      characters: d.characters || [],
      content: d.content || d.description || d.location_description || '',
      order: d.order || 0,
    }
    const res = await api.post('/v1/scenes', payload)
    return res.data
  },

  /** Update a scene via Go backend */
  updateScene: async (id: number, data: {
    title?: string
    description?: string
    location?: string
    timeOfDay?: string
    characters?: string[]
    content?: string
    order?: number
  }): Promise<ApiResponse<any>> => {
    const res = await api.put(`/v1/scenes/${id}`, data)
    return res.data
  },

  /** List scenes from Go backend, returns as SceneTemplate[] for UI compatibility */
  listScenes: async (params?: {
    category?: string; tags?: string; limit?: number
  }): Promise<{ data: SceneTemplate[]; total: number }> => {
    const res = await api.get<{ scenes: GoScene[]; total: number; page: number; pages: number }>(
      '/v1/scenes',
      { params: { page: 1, pageSize: params?.limit || 50 } }
    )
    const body = res.data
    if (body && body.scenes) {
      return {
        data: body.scenes.map((s: GoScene): SceneTemplate => ({
          template_id: String(s.id),
          name: s.title,
          category: s.location || '',
          location_description: s.description || '',
          lighting_setup: {},
          camera_setups: [],
          reference_images: [],
          usage_count: 0,
          tags: [],
          visibility: 'private',
          version: 1,
        })),
        total: body.total,
      }
    }
    return { data: [], total: 0 }
  },

  getScene: async (templateId: string): Promise<ApiResponse<{ data: SceneTemplate }>> => {
    const res = await api.get(`/v1/scenes/${templateId}`)
    return { success: true, data: { data: res.data }, code: 200, message: 'ok' } as any
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
