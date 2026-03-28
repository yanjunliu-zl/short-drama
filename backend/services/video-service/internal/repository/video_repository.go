package repository

import (
	"context"
	"fmt"
	"sort"
	"time"
	"short-drama-platform/video-service/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type VideoRepository interface {
	// 视频操作
	Create(ctx context.Context, video *model.Video) error
	FindByID(ctx context.Context, id string) (*model.Video, error)
	FindByUserID(ctx context.Context, userID string, status string, page, pageSize int) ([]*model.Video, error)
	CountByUserID(ctx context.Context, userID string, status string) (int64, error)
	Update(ctx context.Context, video *model.Video) error
	Delete(ctx context.Context, id string) error

	// 视频处理任务
	CreateProcessingJob(ctx context.Context, job *model.VideoProcessingJob) error
	FindProcessingJobByID(ctx context.Context, id string) (*model.VideoProcessingJob, error)
	FindProcessingJobsByVideoID(ctx context.Context, videoID string) ([]*model.VideoProcessingJob, error)
	UpdateProcessingJob(ctx context.Context, job *model.VideoProcessingJob) error

	// 视频使用记录
	CreateUsageRecord(ctx context.Context, usage *model.VideoUsage) error
}

// 模拟实现 - 使用内存存储
type mockVideoRepository struct {
	videos            []*model.Video
	processingJobs    []*model.VideoProcessingJob
	usageRecords      []*model.VideoUsage
}

func NewVideoRepository(conn sqlx.SqlConn) VideoRepository {
	// 返回模拟实现，稍后替换为数据库实现
	return newMockVideoRepository()
}

func newMockVideoRepository() *mockVideoRepository {
	repo := &mockVideoRepository{
		videos:         make([]*model.Video, 0),
		processingJobs: make([]*model.VideoProcessingJob, 0),
		usageRecords:   make([]*model.VideoUsage, 0),
	}

	// 初始化一些模拟数据
	repo.initMockData()
	return repo
}

func (r *mockVideoRepository) initMockData() {
	// 视频模拟数据
	r.videos = []*model.Video{
		{
			ID:          "1",
			Title:       "示例视频1",
			Description: "这是一个示例视频",
			UserID:      "user123",
			FileName:    "sample1.mp4",
			FileSize:    1024000,
			FileFormat:  "mp4",
			Status:      model.VideoStatusProcessed,
			Progress:    100,
			CreatedAt:   time.Now().Add(-24 * time.Hour),
			UpdatedAt:   time.Now().Add(-12 * time.Hour),
			ProcessedAt: time.Now().Add(-12 * time.Hour),
		},
		{
			ID:          "2",
			Title:       "示例视频2",
			Description: "正在处理的视频",
			UserID:      "user123",
			FileName:    "sample2.avi",
			FileSize:    2048000,
			FileFormat:  "avi",
			Status:      model.VideoStatusProcessing,
			Progress:    50,
			CreatedAt:   time.Now().Add(-1 * time.Hour),
			UpdatedAt:   time.Now(),
		},
	}
}

func (r *mockVideoRepository) Create(ctx context.Context, video *model.Video) error {
	video.ID = fmt.Sprintf("video_%d", len(r.videos)+1)
	video.CreatedAt = time.Now()
	video.UpdatedAt = time.Now()
	if video.Status == "" {
		video.Status = model.VideoStatusUploaded
	}
	if video.Progress == 0 {
		video.Progress = 0
	}

	r.videos = append(r.videos, video)
	return nil
}

func (r *mockVideoRepository) FindByID(ctx context.Context, id string) (*model.Video, error) {
	for _, video := range r.videos {
		if video.ID == id {
			return video, nil
		}
	}
	return nil, fmt.Errorf("video not found: %s", id)
}

func (r *mockVideoRepository) FindByUserID(ctx context.Context, userID string, status string, page, pageSize int) ([]*model.Video, error) {
	var filtered []*model.Video
	for _, video := range r.videos {
		if video.UserID == userID || userID == "" {
			if status == "" || string(video.Status) == status {
				filtered = append(filtered, video)
			}
		}
	}

	// 按创建时间倒序排序
	sort.Slice(filtered, func(i, j int) bool {
		return filtered[i].CreatedAt.After(filtered[j].CreatedAt)
	})

	// 分页
	start := (page - 1) * pageSize
	if start >= len(filtered) {
		return []*model.Video{}, nil
	}
	end := start + pageSize
	if end > len(filtered) {
		end = len(filtered)
	}

	return filtered[start:end], nil
}

func (r *mockVideoRepository) CountByUserID(ctx context.Context, userID string, status string) (int64, error) {
	var count int64
	for _, video := range r.videos {
		if video.UserID == userID || userID == "" {
			if status == "" || string(video.Status) == status {
				count++
			}
		}
	}
	return count, nil
}

func (r *mockVideoRepository) Update(ctx context.Context, video *model.Video) error {
	for i, v := range r.videos {
		if v.ID == video.ID {
			video.UpdatedAt = time.Now()
			r.videos[i] = video
			return nil
		}
	}
	return fmt.Errorf("video not found: %s", video.ID)
}

func (r *mockVideoRepository) Delete(ctx context.Context, id string) error {
	for i, video := range r.videos {
		if video.ID == id {
			r.videos = append(r.videos[:i], r.videos[i+1:]...)
			return nil
		}
	}
	return fmt.Errorf("video not found: %s", id)
}

func (r *mockVideoRepository) CreateProcessingJob(ctx context.Context, job *model.VideoProcessingJob) error {
	job.ID = fmt.Sprintf("job_%d", len(r.processingJobs)+1)
	job.CreatedAt = time.Now()
	job.UpdatedAt = time.Now()
	if job.Status == "" {
		job.Status = "pending"
	}

	r.processingJobs = append(r.processingJobs, job)
	return nil
}

func (r *mockVideoRepository) FindProcessingJobByID(ctx context.Context, id string) (*model.VideoProcessingJob, error) {
	for _, job := range r.processingJobs {
		if job.ID == id {
			return job, nil
		}
	}
	return nil, fmt.Errorf("processing job not found: %s", id)
}

func (r *mockVideoRepository) FindProcessingJobsByVideoID(ctx context.Context, videoID string) ([]*model.VideoProcessingJob, error) {
	var result []*model.VideoProcessingJob
	for _, job := range r.processingJobs {
		if job.VideoID == videoID {
			result = append(result, job)
		}
	}
	return result, nil
}

func (r *mockVideoRepository) UpdateProcessingJob(ctx context.Context, job *model.VideoProcessingJob) error {
	for i, j := range r.processingJobs {
		if j.ID == job.ID {
			job.UpdatedAt = time.Now()
			r.processingJobs[i] = job
			return nil
		}
	}
	return fmt.Errorf("processing job not found: %s", job.ID)
}

func (r *mockVideoRepository) CreateUsageRecord(ctx context.Context, usage *model.VideoUsage) error {
	usage.ID = int64(len(r.usageRecords) + 1)
	usage.CreatedAt = time.Now()
	r.usageRecords = append(r.usageRecords, usage)
	return nil
}