export interface Video {
  id: string
  title: string
  description?: string
  script_id: string
  status: VideoStatus
  duration_seconds: number
  file_size_bytes?: number
  file_format: VideoFormat
  resolution: VideoResolution
  thumbnail_url?: string
  video_url?: string
  processing_progress: number
  error_message?: string
  user_id: number
  created_at: string
  updated_at: string
  completed_at?: string
}

export interface VideoGenerationRequest {
  script_id: string
  title: string
  description?: string
  style: VideoStyle
  resolution: VideoResolution
  format: VideoFormat
  include_subtitles: boolean
  include_background_music: boolean
  voice_style: VoiceStyle
  additional_requirements?: string
}

export interface VideoUpdateRequest {
  title?: string
  description?: string
  status?: VideoStatus
}

export interface VideoResponse {
  task_id: string
  status: 'processing' | 'completed' | 'failed'
  message: string
  video?: Video
}

export interface VideoListResponse {
  videos: Video[]
  total: number
  page: number
  page_size: number
}

// 枚举类型
export enum VideoStatus {
  Pending = 'pending',
  Processing = 'processing',
  Rendering = 'rendering',
  Encoding = 'encoding',
  Completed = 'completed',
  Failed = 'failed',
  Cancelled = 'cancelled',
}

export enum VideoFormat {
  MP4 = 'mp4',
  MOV = 'mov',
  AVI = 'avi',
  MKV = 'mkv',
  WebM = 'webm',
  GIF = 'gif',
}

export enum VideoResolution {
  SD = 'sd',      // 480p
  HD = 'hd',      // 720p
  FullHD = 'fullhd', // 1080p
  TwoK = '2k',    // 1440p
  FourK = '4k',   // 2160p
}

export enum VideoStyle {
  Cinematic = 'cinematic',
  Documentary = 'documentary',
  Animated = 'animated',
  LiveAction = 'live_action',
  Mixed = 'mixed',
  Minimalist = 'minimalist',
}

export enum VoiceStyle {
  Natural = 'natural',
  Professional = 'professional',
  Casual = 'casual',
  Dramatic = 'dramatic',
  Humorous = 'humorous',
  Storyteller = 'storyteller',
}

// 视频处理状态
export interface VideoProcessingStatus {
  task_id: string
  status: 'pending' | 'processing' | 'rendering' | 'encoding' | 'completed' | 'failed'
  progress: number
  current_step: VideoProcessingStep
  estimated_time_remaining?: number
  result?: Video
  error_message?: string
  created_at: string
  updated_at: string
}

export enum VideoProcessingStep {
  Initializing = 'initializing',
  AssetCollection = 'asset_collection',
  SceneGeneration = 'scene_generation',
  VoiceSynthesis = 'voice_synthesis',
  VideoRendering = 'video_rendering',
  EffectsAdding = 'effects_adding',
  SubtitlesAdding = 'subtitles_adding',
  Encoding = 'encoding',
  Finalizing = 'finalizing',
}