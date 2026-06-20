package repository

import (
	"context"
	"short-drama-platform/user-service/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// UserRepository 用户数据仓库接口
type UserRepository interface {
	Create(ctx context.Context, user *model.User) (int64, error)
	FindByID(ctx context.Context, id int64) (*model.User, error)
	FindByUsername(ctx context.Context, username string) (*model.User, error)
	FindByEmail(ctx context.Context, email string) (*model.User, error)
	Update(ctx context.Context, user *model.User) error
	Delete(ctx context.Context, id int64) error
	List(ctx context.Context, page, pageSize int) ([]*model.User, error)
	Count(ctx context.Context) (int64, error)

	// 用户 Profile
	UpsertProfile(ctx context.Context, profile *model.UserProfile) error
	FindProfileByUserID(ctx context.Context, userID int64) (*model.UserProfile, error)

	// 用户 Session
	CreateSession(ctx context.Context, session *model.UserSession) error
}

// mysqlUserRepository MySQL 实现
type mysqlUserRepository struct {
	conn sqlx.SqlConn
}

// NewUserRepository 创建 MySQL 用户仓库实例
func NewUserRepository(conn sqlx.SqlConn) UserRepository {
	return &mysqlUserRepository{conn: conn}
}

// ==============================
// 用户 CRUD
// ==============================

var createUserSQL = `INSERT INTO users (username, email, password_hash, phone, avatar, status, role, last_login_at, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`

func (r *mysqlUserRepository) Create(ctx context.Context, user *model.User) (int64, error) {
	result, err := r.conn.ExecCtx(ctx, createUserSQL,
		user.Username, user.Email, user.PasswordHash, user.Phone, user.Avatar,
		user.Status, user.Role, user.LastLoginAt, user.CreatedAt, user.UpdatedAt)
	if err != nil {
		return 0, err
	}
	return result.LastInsertId()
}

var findUserByIDSQL = `SELECT id, username, email, password_hash, phone, avatar, status, role, last_login_at, created_at, updated_at
	FROM users WHERE id = ? LIMIT 1`

func (r *mysqlUserRepository) FindByID(ctx context.Context, id int64) (*model.User, error) {
	var user model.User
	err := r.conn.QueryRowCtx(ctx, &user, findUserByIDSQL, id)
	if err != nil {
		return nil, err
	}
	return &user, nil
}

var findUserByUsernameSQL = `SELECT id, username, email, password_hash, phone, avatar, status, role, last_login_at, created_at, updated_at
	FROM users WHERE username = ? LIMIT 1`

func (r *mysqlUserRepository) FindByUsername(ctx context.Context, username string) (*model.User, error) {
	var user model.User
	err := r.conn.QueryRowCtx(ctx, &user, findUserByUsernameSQL, username)
	if err != nil {
		return nil, err
	}
	return &user, nil
}

var findUserByEmailSQL = `SELECT id, username, email, password_hash, phone, avatar, status, role, last_login_at, created_at, updated_at
	FROM users WHERE email = ? LIMIT 1`

func (r *mysqlUserRepository) FindByEmail(ctx context.Context, email string) (*model.User, error) {
	var user model.User
	err := r.conn.QueryRowCtx(ctx, &user, findUserByEmailSQL, email)
	if err != nil {
		return nil, err
	}
	return &user, nil
}

var updateUserSQL = `UPDATE users SET username=?, email=?, password_hash=?, phone=?, avatar=?, status=?, role=?, last_login_at=?, updated_at=?
	WHERE id=?`

func (r *mysqlUserRepository) Update(ctx context.Context, user *model.User) error {
	_, err := r.conn.ExecCtx(ctx, updateUserSQL,
		user.Username, user.Email, user.PasswordHash, user.Phone, user.Avatar,
		user.Status, user.Role, user.LastLoginAt, user.UpdatedAt, user.ID)
	return err
}

var deleteUserSQL = `DELETE FROM users WHERE id = ?`

func (r *mysqlUserRepository) Delete(ctx context.Context, id int64) error {
	_, err := r.conn.ExecCtx(ctx, deleteUserSQL, id)
	return err
}

var listUsersSQL = `SELECT id, username, email, password_hash, phone, avatar, status, role, last_login_at, created_at, updated_at
	FROM users ORDER BY id DESC LIMIT ? OFFSET ?`

func (r *mysqlUserRepository) List(ctx context.Context, page, pageSize int) ([]*model.User, error) {
	offset := (page - 1) * pageSize
	var users []*model.User
	err := r.conn.QueryRowsCtx(ctx, &users, listUsersSQL, pageSize, offset)
	if err != nil {
		return nil, err
	}
	return users, nil
}

var countUsersSQL = `SELECT COUNT(*) FROM users`

func (r *mysqlUserRepository) Count(ctx context.Context) (int64, error) {
	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, countUsersSQL)
	return count, err
}

// ==============================
// 用户 Profile
// ==============================

var upsertProfileSQL = `INSERT INTO user_profiles (user_id, full_name, gender, birthday, bio, website, social_links, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), NOW())
	ON DUPLICATE KEY UPDATE full_name=VALUES(full_name), gender=VALUES(gender), birthday=VALUES(birthday), bio=VALUES(bio), website=VALUES(website), social_links=VALUES(social_links), updated_at=NOW()`

func (r *mysqlUserRepository) UpsertProfile(ctx context.Context, profile *model.UserProfile) error {
	_, err := r.conn.ExecCtx(ctx, upsertProfileSQL,
		profile.UserID, profile.FullName, profile.Gender, profile.Birthday,
		profile.Bio, profile.Website, profile.SocialLinks,
	)
	return err
}

var findProfileSQL = `SELECT user_id, full_name, gender, birthday, bio, website, social_links, created_at, updated_at
	FROM user_profiles WHERE user_id = ?`

func (r *mysqlUserRepository) FindProfileByUserID(ctx context.Context, userID int64) (*model.UserProfile, error) {
	var profile model.UserProfile
	err := r.conn.QueryRowCtx(ctx, &profile, findProfileSQL, userID)
	if err != nil {
		return nil, err
	}
	return &profile, nil
}

// ==============================
// 用户 Session
// ==============================

var createSessionSQL = `INSERT INTO user_sessions (id, user_id, access_token, refresh_token, expires_at, created_at)
	VALUES (?, ?, ?, ?, ?, NOW())`

func (r *mysqlUserRepository) CreateSession(ctx context.Context, session *model.UserSession) error {
	_, err := r.conn.ExecCtx(ctx, createSessionSQL,
		session.ID, session.UserID, session.AccessToken, session.RefreshToken, session.ExpiresAt,
	)
	return err
}
