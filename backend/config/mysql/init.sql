-- Short Drama Platform - 数据库初始化脚本

CREATE TABLE IF NOT EXISTS `users` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `username` VARCHAR(64) NOT NULL DEFAULT '',
    `email` VARCHAR(128) NOT NULL DEFAULT '',
    `password_hash` VARCHAR(255) NOT NULL DEFAULT '',
    `phone` VARCHAR(32) NOT NULL DEFAULT '',
    `avatar` VARCHAR(512) NOT NULL DEFAULT '',
    `status` INT NOT NULL DEFAULT 0 COMMENT '0: inactive, 1: active, 2: suspended',
    `role` INT NOT NULL DEFAULT 0 COMMENT '0: user, 1: admin, 2: superadmin',
    `last_login_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_profiles` (
    `user_id` BIGINT NOT NULL,
    `full_name` VARCHAR(128) NOT NULL DEFAULT '',
    `gender` INT NOT NULL DEFAULT 0 COMMENT '0: unknown, 1: male, 2: female',
    `birthday` DATE NULL,
    `bio` TEXT,
    `website` VARCHAR(512) NOT NULL DEFAULT '',
    `social_links` TEXT COMMENT 'JSON format',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`user_id`),
    CONSTRAINT `fk_profile_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_sessions` (
    `id` VARCHAR(64) NOT NULL,
    `user_id` BIGINT NOT NULL,
    `access_token` VARCHAR(512) NOT NULL DEFAULT '',
    `refresh_token` VARCHAR(512) NOT NULL DEFAULT '',
    `expires_at` DATETIME NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    CONSTRAINT `fk_session_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Content Service Tables

CREATE TABLE IF NOT EXISTS `cases` (
    `id` VARCHAR(64) NOT NULL,
    `title` VARCHAR(256) NOT NULL DEFAULT '',
    `description` TEXT,
    `author` VARCHAR(128) NOT NULL DEFAULT '',
    `cover_url` VARCHAR(512) NOT NULL DEFAULT '',
    `genre` VARCHAR(64) NOT NULL DEFAULT '',
    `tags` VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'comma-separated',
    `status` VARCHAR(32) NOT NULL DEFAULT 'published',
    `view_count` BIGINT NOT NULL DEFAULT 0,
    `like_count` BIGINT NOT NULL DEFAULT 0,
    `share_count` BIGINT NOT NULL DEFAULT 0,
    `user_id` VARCHAR(64) NOT NULL DEFAULT '',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `works` (
    `id` VARCHAR(64) NOT NULL,
    `case_id` VARCHAR(64) NOT NULL DEFAULT '',
    `user_id` VARCHAR(64) NOT NULL DEFAULT '',
    `title` VARCHAR(256) NOT NULL DEFAULT '',
    `description` TEXT,
    `status` VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT 'draft, editing, completed, exported',
    `progress` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_case_id` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `scenes` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `case_id` VARCHAR(64) NOT NULL DEFAULT '',
    `title` VARCHAR(256) NOT NULL DEFAULT '',
    `description` TEXT,
    `location` VARCHAR(256) NOT NULL DEFAULT '',
    `time_of_day` VARCHAR(64) NOT NULL DEFAULT '',
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_case_id` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `characters` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `case_id` VARCHAR(64) NOT NULL DEFAULT '',
    `name` VARCHAR(128) NOT NULL DEFAULT '',
    `role` VARCHAR(64) NOT NULL DEFAULT '',
    `description` TEXT,
    `avatar_url` VARCHAR(512) NOT NULL DEFAULT '',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_case_id` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `script_outlines` (
    `id` VARCHAR(64) NOT NULL,
    `case_id` VARCHAR(64) NOT NULL DEFAULT '',
    `content` TEXT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_case_id` (`case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User interactions (recommendation system)
CREATE TABLE IF NOT EXISTS user_case_interactions (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL,
    case_id VARCHAR(64) NOT NULL,
    action_type VARCHAR(16) NOT NULL DEFAULT 'view',
    recall_source VARCHAR(32) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_user (user_id),
    KEY idx_case (case_id),
    KEY idx_action (action_type),
    KEY idx_user_time (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Comments table
CREATE TABLE IF NOT EXISTS comments (
    id BIGINT NOT NULL AUTO_INCREMENT,
    case_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    username VARCHAR(128) NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    parent_id BIGINT DEFAULT NULL,
    like_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_case (case_id),
    KEY idx_user (user_id),
    KEY idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Assets table
CREATE TABLE IF NOT EXISTS assets (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(256) NOT NULL DEFAULT '',
    type VARCHAR(64) NOT NULL DEFAULT '',
    count INT NOT NULL DEFAULT 0,
    access_level VARCHAR(32) NOT NULL DEFAULT 'private',
    owner_id VARCHAR(64) NOT NULL DEFAULT '',
    is_personal BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT,
    last_update DATE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_owner (owner_id),
    KEY idx_type (type),
    KEY idx_personal (is_personal)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

