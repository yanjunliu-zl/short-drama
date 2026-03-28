package repository

import (
	"context"
	"short-drama-platform/content-service/internal/types"
)

type WorkRepository interface {
	// 定义作品仓库接口
}

type workRepository struct {
	// 数据库连接等
}

func NewWorkRepository(conn interface{}) WorkRepository {
	return &workRepository{}
}