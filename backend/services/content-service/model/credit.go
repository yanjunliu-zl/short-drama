package model

import "time"

// UserCredit 用户信用额度
type UserCredit struct {
	ID        int64     `db:"id"         json:"id"`
	UserID    string    `db:"user_id"    json:"userId"`
	Balance   int64     `db:"balance"    json:"balance"` // 余额（分）
	CreatedAt time.Time `db:"created_at" json:"createdAt"`
	UpdatedAt time.Time `db:"updated_at" json:"updatedAt"`
}
