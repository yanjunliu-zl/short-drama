package types

// 视频比例
type VideoRatio int

const (
	VideoRatioSquare   VideoRatio = 1 // 1:1
	VideoRatioPortrait VideoRatio = 2 // 9:16
	VideoRatioLandscape VideoRatio = 3 // 16:9
	VideoRatioCinema   VideoRatio = 4 // 21:9
)

// 创作模式
type CreationMode int

const (
	CreationModeScript  CreationMode = 1 // 脚本创作
	CreationModeStory   CreationMode = 2 // 故事创作
	CreationModeTopic   CreationMode = 3 // 主题创作
	CreationModeScripted CreationMode = 4 // 有脚本演绎
	CreationModeImprovisation CreationMode = 5 // 无脚本演绎
)

// 风格参考
type StyleReference int

const (
	StyleReferenceRealistic StyleReference = 1 // 真实风格
	StyleReferenceAnime    StyleReference = 2 // 动漫风格
	StyleReferenceCartoon  StyleReference = 3 // 卡通风格
	StyleReferenceOil      StyleReference = 4 // 油画风格
	StyleReferenceWatercolor StyleReference = 5 // 水彩风格
	StyleReferencePixel    StyleReference = 6 // 像素风格
	StyleReferenceSketch   StyleReference = 7 // 素描风格
)

// 概览信息请求
type OverviewRequest struct {
	UserID int64 `path:"userId"`
}

// 概览信息响应
type OverviewResponse struct {
	UserID         int64        `json:"user_id"`
	VideoRatios    []VideoRatioInfo    `json:"video_ratios"`
	CreationModes  []CreationModeInfo  `json:"creation_modes"`
	StyleReferences []StyleReferenceInfo `json:"style_references"`
	TotalVideos    int64        `json:"total_videos"`
	TotalDuration  int64        `json:"total_duration"`
	LastUpdated    string       `json:"last_updated"`
}

// 视频比例信息
type VideoRatioInfo struct {
	Ratio    VideoRatio `json:"ratio"`
	Name     string     `json:"name"`
	Count    int64      `json:"count"`
	Percentage float64   `json:"percentage"`
}

// 创作模式信息
type CreationModeInfo struct {
	Mode    CreationMode `json:"mode"`
	Name    string       `json:"name"`
	Count   int64        `json:"count"`
	Percentage float64   `json:"percentage"`
}

// 风格参考信息
type StyleReferenceInfo struct {
	Style   StyleReference `json:"style"`
	Name    string         `json:"name"`
	Count   int64          `json:"count"`
	Percentage float64    `json:"percentage"`
}

// 设置概览配置请求
type SetOverviewConfigRequest struct {
	UserID          int64        `json:"user_id"`
	VideoRatio      *VideoRatio  `json:"video_ratio,omitempty"`
	CreationMode    *CreationMode `json:"creation_mode,omitempty"`
	StyleReference  *StyleReference `json:"style_reference,omitempty"`
}

// 设置概览配置响应
type SetOverviewConfigResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}
