package repository

// (no imports needed currently)

type WorkRepository interface {
	// 定义作品仓库接口
}

type workRepository struct {
	// 数据库连接等
}

func NewWorkRepository(conn interface{}) WorkRepository {
	return &workRepository{}
}