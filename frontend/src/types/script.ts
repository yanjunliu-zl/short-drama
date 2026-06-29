import { Gender } from './user'

export interface Script {
  id: string
  title: string
  description?: string
  content: string
  genre: ScriptGenre
  duration_minutes: number
  character_count: number
  scene_count: number
  status: ScriptStatus
  user_id: number
  created_at: string
  updated_at: string
  completed_at?: string
}

export interface ScriptCharacter {
  id: string
  script_id: string
  name: string
  role: CharacterRole
  age?: number
  gender: Gender
  personality?: string
  background?: string
  appearance?: string
}

export interface ScriptScene {
  id: string
  script_id: string
  scene_number: number
  title: string
  description: string
  location: string
  time_of_day: TimeOfDay
  characters_involved: string[]
  dialogue: string
  stage_directions?: string
  duration_seconds: number
}

export interface ScriptGenerationRequest {
  title: string
  description?: string
  genre: ScriptGenre
  target_duration_minutes: number
  character_count: number
  style?: ScriptStyle
  theme?: string
  additional_requirements?: string
}

export interface ScriptUpdateRequest {
  title?: string
  description?: string
  content?: string
  status?: ScriptStatus
}

export interface ScriptResponse {
  task_id: string
  status: 'processing' | 'completed' | 'failed'
  message: string
  script?: Script
}

export interface ScriptListResponse {
  scripts: Script[]
  total: number
  page: number
  page_size: number
}

// 枚举类型
export enum ScriptStatus {
  Draft = 'draft',
  Generating = 'generating',
  Generated = 'generated',
  Reviewing = 'reviewing',
  Approved = 'approved',
  Rejected = 'rejected',
  Published = 'published',
}

export enum ScriptGenre {
  Romance = 'romance',
  Comedy = 'comedy',
  Drama = 'drama',
  Horror = 'horror',
  Fantasy = 'fantasy',
  SciFi = 'sci-fi',
  Mystery = 'mystery',
  Thriller = 'thriller',
  Action = 'action',
  Adventure = 'adventure',
  Historical = 'historical',
  Family = 'family',
}

export enum CharacterRole {
  Protagonist = 'protagonist',
  Antagonist = 'antagonist',
  Supporting = 'supporting',
  Minor = 'minor',
  Extra = 'extra',
}

export enum TimeOfDay {
  Morning = 'morning',
  Afternoon = 'afternoon',
  Evening = 'evening',
  Night = 'night',
  Dawn = 'dawn',
  Dusk = 'dusk',
}

export enum ScriptStyle {
  Formal = 'formal',
  Casual = 'casual',
  Poetic = 'poetic',
  Humorous = 'humorous',
  Dramatic = 'dramatic',
  Suspenseful = 'suspenseful',
}

// 生成状态类型
export interface GenerationStatus {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  estimated_time_remaining?: number
  result?: Script
  error_message?: string
  created_at: string
  updated_at: string
}

// ========== 分镜头 (Shot) 类型 ==========

export interface Shot {
  id: number
  number: number
  shotType: string
  duration: number
  cameraAngle: string
  sceneRef: string
  characters: string[]
  description: string
  dialogue: string
  soundEffects: string[]
  music: string
  notes: string
  // 三层提示词
  imagePrompt?: string
  imagePromptZh?: string
  videoPrompt?: string
  videoPromptZh?: string
  endFramePrompt?: string
  endFramePromptZh?: string
  needsEndFrame?: boolean
  // 灯光
  lightingStyle?: string
  lightingDirection?: string
  colorTemperature?: string
  lightingNotes?: string
  // 焦点
  depthOfField?: string
  focusTarget?: string
  focusTransition?: string
  // 设备
  cameraRig?: string
  movementSpeed?: string
  cameraMovement?: string
  focalLength?: string
  photographyTechnique?: string
  // 情绪与叙事
  emotionTags?: string[]
  narrativeFunction?: string
  // 氛围
  atmosphericEffects?: string
  effectIntensity?: string
  // 连续性
  continuityRef?: string
  playbackSpeed?: string
}

export interface ReferenceImages {
  characters: Record<string, string>   // name → image_url
  scenes: Record<string, string>       // name → image_url
  props: Record<string, string>        // name → image_url
}

export interface ShotEpisode {
  id: string
  title: string
  number: number
  shots: Shot[]
  description?: string
  referenceImages?: ReferenceImages
}

export interface ShotGenerationResponse {
  task_id: string
  status: 'processing' | 'completed' | 'failed'
  message: string
  episodes?: ShotEpisode[]
}

export interface ShotVideoResultItem {
  shot_id: number
  shot_number: number
  episode_id: string
  episode_title: string
  status: 'completed' | 'failed'
  video_url?: string
  image_url?: string
  file_size?: number
  error?: string
}

// ========== 上传剧本并分集 类型 ==========

/** 后端返回的单集剧本 */
export interface EpisodeItem {
  episode_number: number
  title: string
  content: string
}

/** POST /scripts/split 返回 */
export interface ScriptSplitResponse {
  script_id: number
  title: string
  episodes: EpisodeItem[]
  total_episodes: number
}