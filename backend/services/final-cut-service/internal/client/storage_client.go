package client

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"short-drama-platform/final-cut-service/internal/config"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/zeromicro/go-zero/core/logx"
)

// StorageType 存储类型
const (
	StorageS3    = "s3"
	StorageMinIO = "minio"
	StorageCeph  = "ceph"
	StorageLocal = "local"
)

// StorageClient 对象存储客户端
type StorageClient struct {
	config      config.StorageConfig
	client      *minio.Client
	httpClient  *http.Client
	localBasePath string
}

// NewStorageClient 创建对象存储客户端
func NewStorageClient(cfg config.Config) (*StorageClient, error) {
	storageCfg := cfg.Storage
	client := &StorageClient{
		config:        storageCfg,
		localBasePath: "/app/storage",
	}

	// 初始化本地存储路径
	if err := os.MkdirAll(client.localBasePath, 0755); err != nil {
		logx.Errorf("failed to create local storage path: %v", err)
	}

	// 根据存储类型初始化客户端
	switch strings.ToLower(storageCfg.Type) {
	case StorageS3, StorageMinIO, StorageCeph:
		return client.initMinIOClient()
	case StorageLocal:
		logx.Info("using local storage")
		return client, nil
	default:
		logx.Errorf("unknown storage type: %s, using local storage", storageCfg.Type)
		return client, nil
	}
}

// initMinIOClient 初始化 MinIO 客户端
func (c *StorageClient) initMinIOClient() (*StorageClient, error) {
	opts := &minio.Options{
		Creds:  credentials.NewStaticV4(c.config.AccessKey, c.config.SecretKey, ""),
		Secure: false, // 如果使用 HTTP 则设为 false
		Region: c.config.Region,
	}

	minIOClient, err := minio.New(c.config.Endpoint, opts)
	if err != nil {
		logx.Errorf("failed to create minio client: %v", err)
		return nil, err
	}

	c.client = minIOClient
	c.httpClient = &http.Client{Timeout: 30 * time.Second}

	logx.Infof("initialized %s storage client: %s, bucket: %s", c.config.Type, c.config.Endpoint, c.config.Bucket)

	return c, nil
}

// EnsureBucket 确保存储桶存在
func (c *StorageClient) EnsureBucket(ctx context.Context) error {
	if c.config.Type == StorageLocal {
		return nil
	}

	if c.client == nil {
		return fmt.Errorf("storage client is not initialized")
	}

	// 检查桶是否存在
	exists, err := c.client.BucketExists(ctx, c.config.Bucket)
	if err != nil {
		logx.Errorf("failed to check bucket existence: %v", err)
		return err
	}

	if !exists {
		// 创建桶
		if err := c.client.MakeBucket(ctx, c.config.Bucket, minio.MakeBucketOptions{Region: c.config.Region}); err != nil {
			logx.Errorf("failed to create bucket: %v", err)
			return err
		}
		logx.Infof("created bucket: %s", c.config.Bucket)
	}

	return nil
}

// UploadFile 上传文件到对象存储
func (c *StorageClient) UploadFile(ctx context.Context, filePath, objectName string, contentType string) (string, error) {
	if c.config.Type == StorageLocal {
		return c.uploadToLocal(filePath, objectName)
	}

	if c.client == nil {
		return "", fmt.Errorf("storage client is not initialized")
	}

	// 打开文件
	file, err := os.Open(filePath)
	if err != nil {
		logx.Errorf("failed to open file: %v", err)
		return "", err
	}
	defer file.Close()

	// 获取文件信息
	fileInfo, err := file.Stat()
	if err != nil {
		logx.Errorf("failed to get file info: %v", err)
		return "", err
	}

	// 上传文件
	_, err = c.client.PutObject(
		ctx,
		c.config.Bucket,
		objectName,
		file,
		fileInfo.Size(),
		minio.PutObjectOptions{
			ContentType: contentType,
		},
	)
	if err != nil {
		logx.Errorf("failed to upload file to minio: %v", err)
		return "", err
	}

	// 生成预签名URL（有效期7天）
	presignedURL, err := c.client.PresignedGetObject(
		ctx,
		c.config.Bucket,
		objectName,
		7*24*time.Hour,
		nil,
	)
	if err != nil {
		logx.Errorf("failed to generate presigned URL: %v", err)
		return "", err
	}

	logx.Infof("file uploaded successfully: %s -> %s", filePath, objectName)
	return presignedURL.String(), nil
}

// UploadBytes 上传字节数组到对象存储
func (c *StorageClient) UploadBytes(ctx context.Context, data []byte, objectName, contentType string) (string, error) {
	if c.config.Type == StorageLocal {
		return c.uploadBytesToLocal(data, objectName)
	}

	if c.client == nil {
		return "", fmt.Errorf("storage client is not initialized")
	}

	// 使用 MinIO 的 PutObject 上传字节数据
	reader := bytes.NewReader(data)
	_, err := c.client.PutObject(
		ctx,
		c.config.Bucket,
		objectName,
		reader,
		int64(len(data)),
		minio.PutObjectOptions{
			ContentType: contentType,
		},
	)
	if err != nil {
		logx.Errorf("failed to upload bytes to minio: %v", err)
		return "", err
	}

	// 生成预签名URL
	presignedURL, err := c.client.PresignedGetObject(
		ctx,
		c.config.Bucket,
		objectName,
		7*24*time.Hour,
		nil,
	)
	if err != nil {
		logx.Errorf("failed to generate presigned URL: %v", err)
		return "", err
	}

	logx.Infof("bytes uploaded successfully: %s", objectName)
	return presignedURL.String(), nil
}

// UploadFileReader 上传文件流
func (c *StorageClient) UploadFileReader(ctx context.Context, reader multipart.File, size int64, objectName, contentType string) (string, error) {
	if c.config.Type == StorageLocal {
		return c.uploadReaderToLocal(reader, objectName)
	}

	if c.client == nil {
		return "", fmt.Errorf("storage client is not initialized")
	}

	// 上传文件流
	_, err := c.client.PutObject(
		ctx,
		c.config.Bucket,
		objectName,
		reader,
		size,
		minio.PutObjectOptions{
			ContentType: contentType,
		},
	)
	if err != nil {
		logx.Errorf("failed to upload file reader to minio: %v", err)
		return "", err
	}

	// 生成预签名URL
	presignedURL, err := c.client.PresignedGetObject(
		ctx,
		c.config.Bucket,
		objectName,
		7*24*time.Hour,
		nil,
	)
	if err != nil {
		logx.Errorf("failed to generate presigned URL: %v", err)
		return "", err
	}

	logx.Infof("file reader uploaded successfully: %s", objectName)
	return presignedURL.String(), nil
}

// DownloadFile 下载文件
func (c *StorageClient) DownloadFile(ctx context.Context, objectName, filePath string) error {
	if c.config.Type == StorageLocal {
		return c.downloadFromLocal(objectName, filePath)
	}

	if c.client == nil {
		return fmt.Errorf("storage client is not initialized")
	}

	// 下载文件
	reader, err := c.client.GetObject(ctx, c.config.Bucket, objectName, minio.GetObjectOptions{})
	if err != nil {
		logx.Errorf("failed to get object: %v", err)
		return err
	}
	defer reader.Close()

	// 创建文件
	out, err := os.Create(filePath)
	if err != nil {
		logx.Errorf("failed to create file: %v", err)
		return err
	}
	defer out.Close()

	// 复制数据
	_, err = io.Copy(out, reader)
	if err != nil {
		logx.Errorf("failed to copy file: %v", err)
		return err
	}

	logx.Infof("file downloaded successfully: %s -> %s", objectName, filePath)
	return nil
}

// DeleteFile 删除文件
func (c *StorageClient) DeleteFile(ctx context.Context, objectName string) error {
	if c.config.Type == StorageLocal {
		return c.deleteLocalFile(objectName)
	}

	if c.client == nil {
		return fmt.Errorf("storage client is not initialized")
	}

	// 删除文件
	err := c.client.RemoveObject(ctx, c.config.Bucket, objectName, minio.RemoveObjectOptions{})
	if err != nil {
		logx.Errorf("failed to delete object: %v", err)
		return err
	}

	logx.Infof("file deleted successfully: %s", objectName)
	return nil
}

// GetFileURL 获取文件的公开URL
func (c *StorageClient) GetFileURL(objectName string) string {
	if c.config.Type == StorageLocal {
		return fmt.Sprintf("/storage/%s", objectName)
	}

	if c.client == nil {
		return ""
	}

	// 返回对象的URL
	return fmt.Sprintf("http://%s/%s/%s", c.config.Endpoint, c.config.Bucket, objectName)
}

// uploadToLocal 上传文件到本地存储
func (c *StorageClient) uploadToLocal(filePath, objectName string) (string, error) {
	// 确保目录存在
	dirPath := filepath.Dir(filepath.Join(c.localBasePath, objectName))
	if err := os.MkdirAll(dirPath, 0755); err != nil {
		logx.Errorf("failed to create directory: %v", err)
		return "", err
	}

	// 复制文件
	src, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer src.Close()

	dst, err := os.Create(filepath.Join(c.localBasePath, objectName))
	if err != nil {
		return "", err
	}
	defer dst.Close()

	if _, err := io.Copy(dst, src); err != nil {
		return "", err
	}

	logx.Infof("file uploaded to local storage: %s -> %s", filePath, objectName)
	return fmt.Sprintf("/storage/%s", objectName), nil
}

// uploadBytesToLocal 上传字节数组到本地存储
func (c *StorageClient) uploadBytesToLocal(data []byte, objectName string) (string, error) {
	// 确保目录存在
	dirPath := filepath.Dir(filepath.Join(c.localBasePath, objectName))
	if err := os.MkdirAll(dirPath, 0755); err != nil {
		logx.Errorf("failed to create directory: %v", err)
		return "", err
	}

	// 写入文件
	err := os.WriteFile(filepath.Join(c.localBasePath, objectName), data, 0644)
	if err != nil {
		return "", err
	}

	logx.Infof("bytes uploaded to local storage: %s", objectName)
	return fmt.Sprintf("/storage/%s", objectName), nil
}

// uploadReaderToLocal 上传文件流到本地存储
func (c *StorageClient) uploadReaderToLocal(reader multipart.File, objectName string) (string, error) {
	// 确保目录存在
	dirPath := filepath.Dir(filepath.Join(c.localBasePath, objectName))
	if err := os.MkdirAll(dirPath, 0755); err != nil {
		logx.Errorf("failed to create directory: %v", err)
		return "", err
	}

	// 写入文件
	dst, err := os.Create(filepath.Join(c.localBasePath, objectName))
	if err != nil {
		return "", err
	}
	defer dst.Close()

	if _, err := io.Copy(dst, reader); err != nil {
		return "", err
	}

	logx.Infof("file reader uploaded to local storage: %s", objectName)
	return fmt.Sprintf("/storage/%s", objectName), nil
}

// downloadFromLocal 从本地存储下载文件
func (c *StorageClient) downloadFromLocal(objectName, filePath string) error {
	src, err := os.Open(filepath.Join(c.localBasePath, objectName))
	if err != nil {
		return err
	}
	defer src.Close()

	dst, err := os.Create(filePath)
	if err != nil {
		return err
	}
	defer dst.Close()

	if _, err := io.Copy(dst, src); err != nil {
		return err
	}

	logx.Infof("file downloaded from local storage: %s -> %s", objectName, filePath)
	return nil
}

// deleteLocalFile 删除本地文件
func (c *StorageClient) deleteLocalFile(objectName string) error {
	filePath := filepath.Join(c.localBasePath, objectName)
	err := os.Remove(filePath)
	if err != nil {
		return err
	}

	logx.Infof("file deleted from local storage: %s", objectName)
	return nil
}

// Close 关闭存储客户端
func (c *StorageClient) Close() error {
	if c.client != nil {
		// minio client doesn't need explicit shutdown
	}
	return nil
}
