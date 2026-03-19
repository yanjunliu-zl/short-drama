package repository

import (
	"context"
	"short-drama-platform/user-service/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type UserRepository interface {
	Create(ctx context.Context, user *model.User) (int64, error)
	FindByID(ctx context.Context, id int64) (*model.User, error)
	FindByUsername(ctx context.Context, username string) (*model.User, error)
	FindByEmail(ctx context.Context, email string) (*model.User, error)
	Update(ctx context.Context, user *model.User) error
	Delete(ctx context.Context, id int64) error
	List(ctx context.Context, page, pageSize int) ([]*model.User, error)
	Count(ctx context.Context) (int64, error)
}

type userRepository struct {
	conn sqlx.SqlConn
}

func NewUserRepository(conn sqlx.SqlConn) UserRepository {
	return &userRepository{conn: conn}
}

func (r *userRepository) Create(ctx context.Context, user *model.User) (int64, error) {
	query := `INSERT INTO users (
		username, email, password_hash, phone, avatar, status, role,
		last_login_at, created_at, updated_at
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`

	result, err := r.conn.ExecCtx(ctx, query,
		user.Username, user.Email, user.PasswordHash, user.Phone, user.Avatar,
		user.Status, user.Role, user.LastLoginAt, user.CreatedAt, user.UpdatedAt)
	if err != nil {
		return 0, err
	}

	return result.LastInsertId()
}

func (r *userRepository) FindByID(ctx context.Context, id int64) (*model.User, error) {
	query := `SELECT id, username, email, password_hash, phone, avatar, status, role,
		last_login_at, created_at, updated_at FROM users WHERE id = ? LIMIT 1`

	var user model.User
	err := r.conn.QueryRowCtx(ctx, &user, query, id)
	if err != nil {
		return nil, err
	}

	return &user, nil
}

func (r *userRepository) FindByUsername(ctx context.Context, username string) (*model.User, error) {
	query := `SELECT id, username, email, password_hash, phone, avatar, status, role,
		last_login_at, created_at, updated_at FROM users WHERE username = ? LIMIT 1`

	var user model.User
	err := r.conn.QueryRowCtx(ctx, &user, query, username)
	if err != nil {
		return nil, err
	}

	return &user, nil
}

func (r *userRepository) FindByEmail(ctx context.Context, email string) (*model.User, error) {
	query := `SELECT id, username, email, password_hash, phone, avatar, status, role,
		last_login_at, created_at, updated_at FROM users WHERE email = ? LIMIT 1`

	var user model.User
	err := r.conn.QueryRowCtx(ctx, &user, query, email)
	if err != nil {
		return nil, err
	}

	return &user, nil
}

func (r *userRepository) Update(ctx context.Context, user *model.User) error {
	query := `UPDATE users SET
		username = ?, email = ?, password_hash = ?, phone = ?, avatar = ?,
		status = ?, role = ?, last_login_at = ?, updated_at = ?
		WHERE id = ?`

	_, err := r.conn.ExecCtx(ctx, query,
		user.Username, user.Email, user.PasswordHash, user.Phone, user.Avatar,
		user.Status, user.Role, user.LastLoginAt, user.UpdatedAt, user.ID)

	return err
}

func (r *userRepository) Delete(ctx context.Context, id int64) error {
	query := `DELETE FROM users WHERE id = ?`
	_, err := r.conn.ExecCtx(ctx, query, id)
	return err
}

func (r *userRepository) List(ctx context.Context, page, pageSize int) ([]*model.User, error) {
	offset := (page - 1) * pageSize
	query := `SELECT id, username, email, password_hash, phone, avatar, status, role,
		last_login_at, created_at, updated_at FROM users
		ORDER BY id DESC LIMIT ? OFFSET ?`

	var users []*model.User
	err := r.conn.QueryRowsCtx(ctx, &users, query, pageSize, offset)
	if err != nil {
		return nil, err
	}

	return users, nil
}

func (r *userRepository) Count(ctx context.Context) (int64, error) {
	query := `SELECT COUNT(*) FROM users`
	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, query)
	return count, err
}