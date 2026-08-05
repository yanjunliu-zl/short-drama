package consumer

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"short-drama-platform/final-cut-service/internal/svc"

	amqp "github.com/rabbitmq/amqp091-go"
	"github.com/google/uuid"
	"github.com/zeromicro/go-zero/core/logx"
)

// FinalCutTaskMessage 最终剪辑任务消息
type FinalCutTaskMessage struct {
	TaskID    string   `json:"task_id"`
	ProjectID string   `json:"project_id"`
	VideoURLs []string `json:"video_urls"`
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
	if err := c.svcCtx.StorageClient.EnsureBucket(c.ctx); err != nil {
		logx.Errorf("failed to ensure bucket: %v", err)
	}

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
	ctx, cancel := context.WithTimeout(c.ctx, 10*time.Minute)
	defer cancel()

	var msg FinalCutTaskMessage
	if err := json.Unmarshal(d.Body, &msg); err != nil {
		logx.Errorf("failed to unmarshal message: %v", err)
		d.Ack(false)
		return
	}

	logx.Infof("Processing final cut task: %s with %d video URLs", msg.TaskID, len(msg.VideoURLs))

	// 更新任务状态为处理中
	if err := c.svcCtx.FinalCutRepository.UpdateStatus(msg.TaskID, "processing"); err != nil {
		logx.Errorf("failed to update task status: %v", err)
		d.Ack(false)
		return
	}

	c.updateTaskProgress(msg.TaskID, 5)

	// 执行 ffmpeg 拼接
	videoURL, thumbnailURL, duration, err := c.processVideo(ctx, &msg)
	if err != nil {
		logx.Errorf("failed to process video: %v", err)
		c.svcCtx.FinalCutRepository.UpdateError(msg.TaskID, err.Error())
		c.updateTaskProgress(msg.TaskID, 0)
		d.Ack(false)
		return
	}

	c.updateTaskProgress(msg.TaskID, 95)

	// 更新任务结果
	if err := c.svcCtx.FinalCutRepository.UpdateResult(
		msg.TaskID, videoURL, thumbnailURL, duration,
	); err != nil {
		logx.Errorf("failed to update task result: %v", err)
	}

	c.updateTaskProgress(msg.TaskID, 100)

	logx.Infof("Final cut task completed: %s, video: %s, duration: %.1fs", msg.TaskID, videoURL, duration)
	d.Ack(false)
}

// processVideo 使用 ffmpeg 拼接视频
func (c *Consumer) processVideo(ctx context.Context, msg *FinalCutTaskMessage) (string, string, float64, error) {
	if len(msg.VideoURLs) == 0 {
		return "", "", 0, fmt.Errorf("no video URLs provided")
	}

	workDir := filepath.Join("/tmp/final-cut-workdir", msg.TaskID)
	if err := os.MkdirAll(workDir, 0755); err != nil {
		return "", "", 0, fmt.Errorf("failed to create work dir: %w", err)
	}
	defer os.RemoveAll(workDir)

	// Step 1: 下载所有视频文件
	var inputFiles []string
	for i, url := range msg.VideoURLs {
		inputPath := filepath.Join(workDir, fmt.Sprintf("input_%03d.mp4", i))
		logx.Infof("Downloading video %d/%d: %s", i+1, len(msg.VideoURLs), url)

		if err := downloadFile(ctx, url, inputPath); err != nil {
			logx.Errorf("failed to download video %d: %v", i, err)
			continue // skip failed downloads
		}

		// 验证文件是否有效
		if info, err := os.Stat(inputPath); err != nil || info.Size() == 0 {
			logx.Errorf("downloaded file is empty or missing: %s", inputPath)
			continue
		}

		inputFiles = append(inputFiles, inputPath)
	}

	if len(inputFiles) == 0 {
		return "", "", 0, fmt.Errorf("all video downloads failed")
	}

	c.updateTaskProgress(msg.TaskID, 20)

	// Step 2: 创建 concat file list
	fileListPath := filepath.Join(workDir, "filelist.txt")
	fileList, err := os.Create(fileListPath)
	if err != nil {
		return "", "", 0, fmt.Errorf("failed to create filelist: %w", err)
	}
	for _, f := range inputFiles {
		fmt.Fprintf(fileList, "file '%s'\n", f)
	}
	fileList.Close()

	c.updateTaskProgress(msg.TaskID, 30)

	// Step 3: ffmpeg concat — 先尝试 stream copy
	outputPath := filepath.Join(workDir, "output.mp4")

	err = runFFmpeg(ctx,
		"-f", "concat", "-safe", "0", "-i", fileListPath,
		"-c", "copy",
		"-y", outputPath,
	)
	if err != nil {
		logx.Errorf("stream copy failed, trying re-encode: %v", err)
		// Step 4: 回退为重新编码
		err = runFFmpeg(ctx,
			"-f", "concat", "-safe", "0", "-i", fileListPath,
			"-c:v", "libx264", "-preset", "fast", "-crf", "23",
			"-c:a", "aac", "-b:a", "128k",
			"-pix_fmt", "yuv420p",
			"-y", outputPath,
		)
		if err != nil {
			return "", "", 0, fmt.Errorf("ffmpeg concat failed: %w", err)
		}
	}

	c.updateTaskProgress(msg.TaskID, 70)

	// Step 5: ffprobe 获取时长
	duration := getVideoDuration(ctx, outputPath)

	// Step 6: 生成缩略图
	thumbnailPath := filepath.Join(workDir, "thumbnail.jpg")
	runFFmpeg(ctx,
		"-i", outputPath,
		"-ss", "00:00:01",
		"-vframes", "1",
		"-f", "image2",
		"-y", thumbnailPath,
	)

	c.updateTaskProgress(msg.TaskID, 80)

	// Step 7: 上传到 MinIO/Ceph
	videoObjectName := fmt.Sprintf("final-cut/%s/output.mp4", msg.TaskID)
	videoURL, err := c.svcCtx.StorageClient.UploadFile(ctx, outputPath, videoObjectName, "video/mp4")
	if err != nil {
		return "", "", 0, fmt.Errorf("failed to upload video: %w", err)
	}

	var thumbnailURL string
	if _, err := os.Stat(thumbnailPath); err == nil {
		thumbnailObjectName := fmt.Sprintf("final-cut/%s/thumbnail.jpg", msg.TaskID)
		thumbnailURL, _ = c.svcCtx.StorageClient.UploadFile(ctx, thumbnailPath, thumbnailObjectName, "image/jpeg")
	}

	return videoURL, thumbnailURL, duration, nil
}

// downloadFile 下载文件到本地
func downloadFile(ctx context.Context, url, filePath string) error {
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return err
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download failed with status %d", resp.StatusCode)
	}

	out, err := os.Create(filePath)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, resp.Body)
	return err
}

// runFFmpeg 执行 ffmpeg 命令
func runFFmpeg(ctx context.Context, args ...string) error {
	cmd := exec.CommandContext(ctx, "ffmpeg", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		// 截断输出避免日志过大
		outputStr := string(output)
		if len(outputStr) > 500 {
			outputStr = outputStr[len(outputStr)-500:]
		}
		return fmt.Errorf("ffmpeg error: %w, output: %s", err, outputStr)
	}
	return nil
}

// getVideoDuration 获取视频时长（秒）
func getVideoDuration(ctx context.Context, videoPath string) float64 {
	cmd := exec.CommandContext(ctx, "ffprobe",
		"-v", "error",
		"-show_entries", "format=duration",
		"-of", "default=noprint_wrappers=1:nokey=1",
		videoPath,
	)
	output, err := cmd.Output()
	if err != nil {
		logx.Errorf("ffprobe failed: %v", err)
		return 0
	}

	var duration float64
	fmt.Sscanf(string(output), "%f", &duration)
	return duration
}

// updateTaskProgress 更新任务进度
func (c *Consumer) updateTaskProgress(taskID string, progress int) {
	if err := c.svcCtx.FinalCutRepository.UpdateProgress(taskID, progress); err != nil {
		logx.Errorf("failed to update task progress: %v", err)
	}

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

// Stop 停止消费
func (c *Consumer) Stop() error {
	return c.svcCtx.RabbitMQ.Close()
}

// EnsureBucket 确保存储桶存在
func (c *Consumer) EnsureBucket(ctx context.Context) error {
	return c.svcCtx.StorageClient.EnsureBucket(ctx)
}

// 确保 uuid 包被使用（保持兼容）
var _ = uuid.New
