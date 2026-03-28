package repository

import (
	"context"
	"short-drama-platform/content-service/internal/types"
)

type CaseRepository interface {
	// 定义案例仓库接口
}

type caseRepository struct {
	// 数据库连接等
}

func NewCaseRepository(conn interface{}) CaseRepository {
	return &caseRepository{}
}