package repository

import (
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type OverviewRepository struct {
	conn sqlx.SqlConn
}

func NewOverviewRepository(conn sqlx.SqlConn) OverviewRepository {
	return OverviewRepository{conn: conn}
}
