package consumer

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"short-drama-platform/final-cut-service/internal/model"
	"short-drama-platform/final-cut-service/internal/svc"

	amqp "github.com/rabbitmq/amqp091-go"
	"github.com/google/uuid"
	"github.com/zeromicro/go-zero/core/logx"
)

// FinalCutTaskMessage 最终剪辑任务消息
type FinalCutTaskMessage struct {
	TaskID          string   `json:"task_id"`
	ProjectID       string   `json:"project_id"`
	VideoIDs        []string `json:"video_ids"`
	AudioID         string   `json:"audio_id"`
	Transcript      string   `json:"transcript"`
	CutPoints       []CutPoint `json:"cut_points"`
	Effects         []Effect   `json:"effects"`
	FontSize        int        `json:"font_size"`
	FontColor       string     `json:"font_color"`
	BackgroundColor string     `json:"background_color"`
}

// CutPoint 切点信息
type CutPoint struct {
	StartTime float64 `json:"start_time"`
	EndTime   float64 `json:"end_time"`
	SceneID   string  `json:"scene_id"`
}

// Effect 特效信息
type Effect struct {
	Name      string                 `json:"name"`
	StartTime float64                `json:"start_time"`
	EndTime   float64                `json:"end_time"`
	Params    map[string]interface{} `json:"params"`
}

// Consumer 消费者
type Consumer struct {
	ctx       context.Context
	svcCtx    *svc.ServiceContext
	queueName string
}

// NewConsumer 创建消费者
func NewConsumer(ctx context.Context, svcCtx *svc.ServiceContext, queueName string) *Consumer {
	return &Consumer{
		ctx:       ctx,
		svcCtx:    svcCtx,
		queueName: queueName,
	}
}

// Start 开始消费
func (c *Consumer) Start() error {
	// 确保存储桶存在
	if err := c.svcCtx.StorageClient.EnsureBucket(c.ctx); err != nil {
		logx.Errorf("failed to ensure bucket: %v", err)
	}

	// 开始消费队列
	deliveries, err := c.svcCtx.RabbitMQ.Consume(c.queueName, "final-cut-consumer")
	if err != nil {
		return fmt.Errorf("failed to consume queue: %w", err)
	}

	go func() {
		for d := range deliveries {
			c.handleMessage(d)
		}
	}()

	logx.Infof("Started consuming queue: %s", c.queueName)
	return nil
}

// handleMessage 处理消息
func (c *Consumer) handleMessage(d amqp.Delivery) {
	ctx, cancel := context.WithTimeout(c.ctx, 5*time.Minute)
	defer cancel()

	var msg FinalCutTaskMessage
	if err := json.Unmarshal(d.Body, &msg); err != nil {
		logx.Errorf("failed to unmarshal message: %v", err)
		d.Ack(false)
		return
	}

	logx.Infof("Processing final cut task: %s", msg.TaskID)

	// 更新任务状态为处理中
	if err := c.svcCtx.FinalCutRepository.UpdateStatus(msg.TaskID, "processing"); err != nil {
		logx.Errorf("failed to update task status: %v", err)
		d.Ack(false)
		return
	}

	// 更新进度
	c.updateTaskProgress(msg.TaskID, 10)

	// 调用视频服务处理视频
	videoURL, thumbnailURL, duration, err := c.processVideo(ctx, &msg)
	if err != nil {
		logx.Errorf("failed to process video: %v", err)

		// 更新任务状态为失败
		c.svcCtx.FinalCutRepository.UpdateError(msg.TaskID, err.Error())

		// 发送失败消息到死信队列（可选）
		d.Ack(false)
		return
	}

	c.updateTaskProgress(msg.TaskID, 100)

	// 更新任务结果
	if err := c.svcCtx.FinalCutRepository.UpdateResult(
		msg.TaskID,
		videoURL,
		thumbnailURL,
		duration,
	); err != nil {
		logx.Errorf("failed to update task result: %v", err)
	}

	// 上传视频文件到对象存储（如果本地有文件）
	// 这里假设视频文件已经由视频服务处理完成并返回了URL
	// 如果需要重新上传，可以取消注释下面的代码

	// if videoURL != "" {
	// 	// 下载视频文件（如果需要重新上传到对象存储）
	// 	tempPath := filepath.Join("/tmp", fmt.Sprintf("%s.mp4", msg.TaskID))
	// 	defer os.Remove(tempPath)

	// 	if err := c.downloadVideoFromService(videoURL, tempPath); err == nil {
	// 		objectName := fmt.Sprintf("final-cut/%s/output.mp4", msg.TaskID)
	// 		uploadedURL, err := c.svcCtx.StorageClient.UploadFile(ctx, tempPath, objectName, "video/mp4")
	// 		if err != nil {
	// 			logx.Errorf("failed to upload video to storage: %v", err)
	// 		} else {
	// 			logx.Infof("Video uploaded to storage: %s", uploadedURL)
	// 		}
	// 	}
	// }

	logx.Infof("Final cut task completed: %s", msg.TaskID)
	d.Ack(false)
}

// processVideo 处理视频
func (c *Consumer) processVideo(ctx context.Context, msg *FinalCutTaskMessage) (string, string, float64, error) {
	// 调用视频服务处理视频
	resp, err := c.svcCtx.VideoService.ProcessVideo(ctx, &svc.VideoTaskRequest{
		TaskType:   "final-cut",
		VideoIDs:   msg.VideoIDs,
		AudioID:    msg.AudioID,
		OutputFormat: "mp4",
	})
	if err != nil {
		return "", "", 0, fmt.Errorf("failed to process video: %w", err)
	}

	// 等待视频处理完成
	videoURL := resp.VideoURL
	thumbnailURL := resp.Thumbnail

	// 模拟处理时间
	time.Sleep(2 * time.Second)

	// 更新进度
	c.updateTaskProgress(msg.TaskID, 50)

	// 这里可以添加更多的视频处理逻辑
	// 比如：使用ffmpeg进行视频剪辑、添加字幕、特效等

	// 返回处理结果
	return videoURL, thumbnailURL, 60.0, nil
}

// updateTaskProgress 更新任务进度
func (c *Consumer) updateTaskProgress(taskID string, progress int) {
	if err := c.svcCtx.FinalCutRepository.UpdateProgress(taskID, progress); err != nil {
		logx.Errorf("failed to update task progress: %v", err)
	}

	// 更新Redis缓存
	cacheKey := "final_cut:task:" + taskID
	cacheData := map[string]interface{}{
		"task_id":    taskID,
		"status":     "processing",
		"progress":   progress,
		"updated_at": time.Now().Unix(),
	}
	cacheBytes, _ := json.Marshal(cacheData)
	c.svcCtx.Redis.Setex(cacheKey, cacheBytes, 24*time.Hour)
}

// downloadVideoFromService 从视频服务下载视频
func (c *Consumer) downloadVideoFromService(videoURL, filePath string) error {
	// 这里可以实现从视频服务下载视频的逻辑
	// 暂时返回nil，表示不需要下载
	return nil
}

// Stop 停止消费
func (c *Consumer) Stop() error {
	// 关闭RabbitMQ连接
	return c.svcCtx.RabbitMQ.Close()
}

// EnsureBucket 确保存储桶存在
func (c *Consumer) EnsureBucket(ctx context.Context) error {
	return c.svcCtx.StorageClient.EnsureBucket(ctx)
}
