// Package cqrs provides CQRS read models for the content service.
// Read models are denormalized, pre-joined views optimized for query performance.
// They are updated asynchronously via event projection (eventual consistency).
package cqrs

// CaseReadModel is a denormalized view of a case for fast listing.
// Updated when case.created, case.updated, user.updated events fire.
type CaseReadModel struct {
	ID          int64    `db:"id"`
	Title       string   `db:"title"`
	Description string   `db:"description"`
	Genre       string   `db:"genre"`
	CoverURL    string   `db:"cover_url"`
	AuthorName  string   `db:"author_name"`   // Joined from users (denormalized)
	AuthorAvatar string  `db:"author_avatar"` // Joined from users
	LikeCount   int      `db:"like_count"`    // Pre-computed counter
	ViewCount   int      `db:"view_count"`    // Pre-computed counter
	SceneCount  int      `db:"scene_count"`   // Pre-computed
	Tags        []string `db:"-"`             // JSON column
	Status      string   `db:"status"`
	CreatedAt   int64    `db:"created_at"`
	UpdatedAt   int64    `db:"updated_at"`
}

// WorkReadModel is a denormalized view of a work for fast listing.
type WorkReadModel struct {
	ID           int64  `db:"id"`
	CaseID       string `db:"case_id"`
	CaseTitle    string `db:"case_title"`    // Denormalized from cases
	Title        string `db:"title"`
	AuthorName   string `db:"author_name"`   // Denormalized from users
	Status       string `db:"status"`
	LikeCount    int    `db:"like_count"`
	CreatedAt    int64  `db:"created_at"`
	UpdatedAt    int64  `db:"updated_at"`
}

// Table schemas for the read model database (shortdrama_read_models):
//
// CREATE TABLE case_read_models (
//     id BIGINT PRIMARY KEY,
//     title VARCHAR(255) NOT NULL,
//     description TEXT,
//     genre VARCHAR(100),
//     cover_url VARCHAR(500),
//     author_name VARCHAR(100),
//     author_avatar VARCHAR(500),
//     like_count INT DEFAULT 0,
//     view_count INT DEFAULT 0,
//     scene_count INT DEFAULT 0,
//     tags JSON,
//     status VARCHAR(50),
//     created_at BIGINT,
//     updated_at BIGINT,
//     INDEX idx_genre (genre),
//     INDEX idx_status (status),
//     INDEX idx_author (author_name),
//     FULLTEXT idx_search (title, description)
// );
//
// CREATE TABLE work_read_models (
//     id BIGINT PRIMARY KEY,
//     case_id VARCHAR(64),
//     case_title VARCHAR(255),
//     title VARCHAR(255) NOT NULL,
//     author_name VARCHAR(100),
//     status VARCHAR(50),
//     like_count INT DEFAULT 0,
//     created_at BIGINT,
//     updated_at BIGINT,
//     INDEX idx_case (case_id),
//     INDEX idx_status (status),
//     INDEX idx_author (author_name)
// );
