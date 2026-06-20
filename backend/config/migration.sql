-- ============================================================
-- Short Drama Platform — Database Migration
-- All services share a single MySQL database (short_drama)
-- Each service owns its own tables via naming conventions
-- ============================================================

CREATE DATABASE IF NOT EXISTS short_drama
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE short_drama;

-- ============================================================
-- 1. user-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64)   NOT NULL,
    email         VARCHAR(128)  NOT NULL,
    password_hash VARCHAR(256)  NOT NULL,
    phone         VARCHAR(32)   DEFAULT '',
    avatar        VARCHAR(512)  DEFAULT '',
    status        TINYINT       NOT NULL DEFAULT 0 COMMENT '0=inactive,1=active,2=suspended',
    role          TINYINT       NOT NULL DEFAULT 0 COMMENT '0=user,1=admin,2=superadmin',
    last_login_at DATETIME      NULL,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_username (username),
    UNIQUE INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id       BIGINT UNSIGNED PRIMARY KEY,
    full_name     VARCHAR(128)  DEFAULT '',
    gender        TINYINT       DEFAULT 0 COMMENT '0=unknown,1=male,2=female',
    birthday      DATE          NULL,
    bio           TEXT,
    website       VARCHAR(256)  DEFAULT '',
    social_links  JSON,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_sessions (
    id             VARCHAR(128) PRIMARY KEY,
    user_id        BIGINT UNSIGNED NOT NULL,
    access_token   VARCHAR(512) NOT NULL,
    refresh_token  VARCHAR(512) NOT NULL,
    expires_at     DATETIME     NOT NULL,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_sessions_user_id (user_id),
    INDEX idx_user_sessions_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. asset-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS assets (
    id           VARCHAR(64)   PRIMARY KEY,
    name         VARCHAR(256)  NOT NULL,
    type         VARCHAR(64)   NOT NULL COMMENT '3D模型,场景资源,音频资源,视觉特效,文本资源,分镜资源',
    count        INT           NOT NULL DEFAULT 1,
    access_level VARCHAR(64)   DEFAULT '',
    owner_id     VARCHAR(64)   DEFAULT '',
    is_personal  TINYINT(1)    NOT NULL DEFAULT 1,
    description  TEXT,
    last_update  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_assets_type (type),
    INDEX idx_assets_owner (owner_id),
    INDEX idx_assets_personal (is_personal),
    INDEX idx_assets_access (access_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS asset_usages (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    asset_id   VARCHAR(64)  NOT NULL,
    user_id    VARCHAR(64)  NOT NULL,
    usage_type VARCHAR(32)  NOT NULL COMMENT 'use,share,download',
    count      INT          NOT NULL DEFAULT 1,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_asset_usages_asset (asset_id),
    INDEX idx_asset_usages_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS asset_shares (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    asset_id       VARCHAR(64)  NOT NULL,
    owner_id       VARCHAR(64)  NOT NULL,
    target_user_id VARCHAR(64)  NOT NULL,
    status         VARCHAR(32)  NOT NULL DEFAULT 'active' COMMENT 'active,revoked',
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at     DATETIME     NULL,
    INDEX idx_asset_shares_asset (asset_id),
    INDEX idx_asset_shares_owner (owner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 3. payment-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS payment_orders (
    id             VARCHAR(64)   PRIMARY KEY,
    order_no       VARCHAR(128)  NOT NULL,
    transaction_id VARCHAR(256)  DEFAULT '',
    user_id        VARCHAR(64)   NOT NULL,
    amount         BIGINT        NOT NULL COMMENT 'amount in cents',
    currency       VARCHAR(8)    NOT NULL DEFAULT 'CNY',
    method         VARCHAR(32)   NOT NULL COMMENT 'wechat,alipay',
    status         VARCHAR(32)   NOT NULL DEFAULT 'pending' COMMENT 'pending,paid,failed,canceled,refunded',
    subject        VARCHAR(256)  NOT NULL,
    description    TEXT,
    notify_url     VARCHAR(512)  DEFAULT '',
    return_url     VARCHAR(512)  DEFAULT '',
    client_ip      VARCHAR(64)   DEFAULT '',
    expire_time    DATETIME      NOT NULL,
    paid_at        DATETIME      NULL,
    extra          JSON,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_payment_order_no (order_no),
    INDEX idx_payment_user (user_id),
    INDEX idx_payment_status (status),
    INDEX idx_payment_method (method)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS refund_orders (
    id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    refund_no         VARCHAR(128)  NOT NULL,
    payment_order_id  VARCHAR(64)   NOT NULL,
    transaction_id    VARCHAR(256)  DEFAULT '',
    refund_amount     BIGINT        NOT NULL COMMENT 'refund amount in cents',
    total_amount      BIGINT        NOT NULL COMMENT 'original total in cents',
    reason            VARCHAR(512)  NOT NULL,
    status            VARCHAR(32)   NOT NULL DEFAULT 'processing' COMMENT 'processing,success,failed',
    refunded_at       DATETIME      NULL,
    created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_refund_no (refund_no),
    INDEX idx_refund_payment (payment_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4. video-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS videos (
    id           VARCHAR(64)   PRIMARY KEY,
    title        VARCHAR(256)  NOT NULL,
    description  TEXT,
    user_id      VARCHAR(64)   NOT NULL,
    file_name    VARCHAR(256)  NOT NULL,
    file_size    BIGINT        NOT NULL DEFAULT 0,
    file_format  VARCHAR(32)   NOT NULL,
    file_path    VARCHAR(512)  DEFAULT '',
    output_path  VARCHAR(512)  DEFAULT '',
    status       VARCHAR(32)   NOT NULL DEFAULT 'uploaded' COMMENT 'uploaded,processing,processed,failed,cancelled',
    progress     INT           NOT NULL DEFAULT 0,
    error_msg    TEXT,
    metadata     JSON,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    processed_at DATETIME      NULL,
    INDEX idx_videos_user (user_id),
    INDEX idx_videos_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS video_processing_jobs (
    id           VARCHAR(64)   PRIMARY KEY,
    video_id     VARCHAR(64)   NOT NULL,
    job_type     VARCHAR(32)   NOT NULL COMMENT 'transcode,extract_audio,add_subtitle',
    status       VARCHAR(32)   NOT NULL DEFAULT 'pending' COMMENT 'pending,processing,completed,failed',
    progress     INT           NOT NULL DEFAULT 0,
    priority     INT           NOT NULL DEFAULT 1,
    params       JSON,
    result       JSON,
    error        TEXT,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    started_at   DATETIME      NULL,
    completed_at DATETIME      NULL,
    INDEX idx_vpj_video (video_id),
    INDEX idx_vpj_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS video_usages (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    video_id   VARCHAR(64)  NOT NULL,
    user_id    VARCHAR(64)  NOT NULL,
    action     VARCHAR(32)  NOT NULL COMMENT 'view,download,share',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_video_usages_video (video_id),
    INDEX idx_video_usages_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4.1 media_assets — 通用媒体资产表 (Ceph 对象存储)
-- ============================================================

CREATE TABLE IF NOT EXISTS media_assets (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    object_key          VARCHAR(512)    NOT NULL COMMENT 'Ceph 对象 Key（存储路径）',
    bucket              VARCHAR(128)    NOT NULL DEFAULT 'short-drama' COMMENT 'Ceph Bucket 名称',
    media_type          VARCHAR(16)     NOT NULL DEFAULT 'image' COMMENT '媒体类型: image / video',
    content_type        VARCHAR(128)    DEFAULT NULL COMMENT 'MIME 类型，如 image/png, video/mp4',
    file_size           BIGINT          DEFAULT 0 COMMENT '文件大小（字节）',
    original_url        VARCHAR(2048)   DEFAULT NULL COMMENT '原始来源 URL（如 Seedance 返回的 URL）',
    ceph_url            VARCHAR(2048)   DEFAULT NULL COMMENT 'Ceph 预签名 URL 或公开 URL',
    source_service      VARCHAR(64)     NOT NULL DEFAULT 'unknown' COMMENT '来源服务名称',
    related_entity_type VARCHAR(64)     DEFAULT NULL COMMENT '关联实体类型 (scene, storyboard, video, character)',
    related_entity_id   VARCHAR(128)    DEFAULT NULL COMMENT '关联实体 ID',
    user_id             VARCHAR(128)    DEFAULT NULL COMMENT '用户 ID',
    metadata_json       TEXT            DEFAULT NULL COMMENT '额外元数据 (JSON)',
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE INDEX idx_media_assets_obj_key (object_key),
    INDEX idx_media_assets_media_type (media_type),
    INDEX idx_media_assets_source (source_service),
    INDEX idx_media_assets_entity (related_entity_type, related_entity_id),
    INDEX idx_media_assets_user (user_id),
    INDEX idx_media_assets_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. content-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS cases (
    id          VARCHAR(64)   PRIMARY KEY,
    title       VARCHAR(256)  NOT NULL,
    description TEXT,
    author      VARCHAR(128)  DEFAULT '' COMMENT 'author name',
    cover_url   VARCHAR(512)  DEFAULT '',
    genre       VARCHAR(64)   DEFAULT '',
    tags        VARCHAR(512)  DEFAULT '' COMMENT 'comma-separated',
    status      VARCHAR(32)   NOT NULL DEFAULT 'draft' COMMENT 'draft,published,archived',
    view_count  BIGINT        NOT NULL DEFAULT 0,
    like_count  BIGINT        NOT NULL DEFAULT 0,
    share_count BIGINT        NOT NULL DEFAULT 0,
    user_id     VARCHAR(64)   NOT NULL,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cases_user (user_id),
    INDEX idx_cases_genre (genre),
    INDEX idx_cases_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS scenes (
    id          VARCHAR(64)   PRIMARY KEY,
    case_id     VARCHAR(64)   NOT NULL,
    title       VARCHAR(256)  NOT NULL,
    description TEXT,
    location    VARCHAR(256)  DEFAULT '',
    time_of_day VARCHAR(32)   DEFAULT '',
    sort_order  INT           NOT NULL DEFAULT 0,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_scenes_case (case_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS characters (
    id          VARCHAR(64)   PRIMARY KEY,
    case_id     VARCHAR(64)   NOT NULL,
    name        VARCHAR(128)  NOT NULL,
    role        VARCHAR(64)   DEFAULT '',
    description TEXT,
    avatar_url  VARCHAR(512)  DEFAULT '',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_characters_case (case_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS works (
    id          VARCHAR(64)   PRIMARY KEY,
    case_id     VARCHAR(64)   NOT NULL,
    user_id     VARCHAR(64)   NOT NULL,
    title       VARCHAR(256)  NOT NULL,
    description TEXT,
    status      VARCHAR(32)   NOT NULL DEFAULT 'draft' COMMENT 'draft,editing,completed,exported',
    progress    INT           NOT NULL DEFAULT 0,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_works_case (case_id),
    INDEX idx_works_user (user_id),
    INDEX idx_works_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS script_outlines (
    id          VARCHAR(64)   PRIMARY KEY,
    case_id     VARCHAR(64)   NOT NULL UNIQUE,
    content     LONGTEXT,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 6. final-cut-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS final_cut_tasks (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    task_id          VARCHAR(64)   NOT NULL,
    project_id       VARCHAR(64)   NOT NULL,
    status           VARCHAR(32)   NOT NULL DEFAULT 'pending' COMMENT 'pending,processing,completed,failed,cancelled',
    video_ids        JSON,
    audio_id         VARCHAR(64)   DEFAULT '',
    transcript       LONGTEXT,
    cut_points       JSON,
    effects          JSON,
    font_size        INT           DEFAULT 16,
    font_color       VARCHAR(32)   DEFAULT '#FFFFFF',
    background_color VARCHAR(32)   DEFAULT '#000000',
    video_url        VARCHAR(512)  DEFAULT '',
    thumbnail_url    VARCHAR(512)  DEFAULT '',
    duration         DOUBLE        DEFAULT 0,
    progress         INT           NOT NULL DEFAULT 0 COMMENT '0-100',
    error_message    TEXT,
    created_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_fct_task (task_id),
    INDEX idx_fct_project (project_id),
    INDEX idx_fct_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 8. llmhua-service tables (Python — AI 图像/视频生成)
-- ============================================================

CREATE TABLE IF NOT EXISTS video_generation_tasks (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    task_id     VARCHAR(64)   NOT NULL COMMENT '任务UUID',
    scene_id    BIGINT        DEFAULT NULL COMMENT '关联场景ID',
    script_id   BIGINT        DEFAULT NULL COMMENT '关联剧本ID',
    status      VARCHAR(20)   NOT NULL DEFAULT 'pending' COMMENT '任务状态',
    progress    INT           DEFAULT 0 COMMENT '进度 0-100',
    video_url   VARCHAR(512)  DEFAULT NULL COMMENT '生成的视频URL',
    image_url   VARCHAR(512)  DEFAULT NULL COMMENT '生成的图片URL',
    prompt      TEXT          DEFAULT NULL COMMENT '生成提示词',
    parameters  JSON          DEFAULT NULL COMMENT '生成参数',
    error       TEXT          DEFAULT NULL COMMENT '错误信息',
    user_id     VARCHAR(64)   DEFAULT NULL COMMENT '用户ID',
    duration    DOUBLE        DEFAULT NULL COMMENT '视频时长',
    start_time  DOUBLE        DEFAULT NULL,
    end_time    DOUBLE        DEFAULT NULL,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_vgt_task_id (task_id),
    INDEX idx_vgt_status (status),
    INDEX idx_vgt_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 9. scene-extractor tables (Python — 场景抽取)
-- ============================================================

CREATE TABLE IF NOT EXISTS extracted_scenes (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    script_id       BIGINT        DEFAULT NULL COMMENT '关联剧本ID',
    scene_name      VARCHAR(255)  DEFAULT NULL COMMENT '场景名称',
    description     TEXT          DEFAULT NULL COMMENT '场景描述',
    characters_data JSON          DEFAULT NULL COMMENT '角色数据',
    props_data      JSON          DEFAULT NULL COMMENT '道具数据',
    image_url       VARCHAR(512)  DEFAULT NULL COMMENT '场景图片URL',
    style           VARCHAR(100)  DEFAULT NULL COMMENT '风格',
    user_id         VARCHAR(64)   DEFAULT NULL COMMENT '用户ID',
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_es_script (script_id),
    INDEX idx_es_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS extracted_characters (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scene_id    BIGINT        DEFAULT NULL COMMENT '关联场景ID',
    script_id   BIGINT        DEFAULT NULL COMMENT '关联剧本ID',
    name        VARCHAR(100)  NOT NULL COMMENT '角色名称',
    description TEXT          DEFAULT NULL COMMENT '角色描述',
    role_type   VARCHAR(50)   DEFAULT NULL COMMENT '角色类型（主角/配角/龙套）',
    attributes  JSON          DEFAULT NULL COMMENT '角色属性',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ec_scene (scene_id),
    INDEX idx_ec_script (script_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS extracted_props (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scene_id    BIGINT        DEFAULT NULL COMMENT '关联场景ID',
    script_id   BIGINT        DEFAULT NULL COMMENT '关联剧本ID',
    name        VARCHAR(100)  NOT NULL COMMENT '道具名称',
    description TEXT          DEFAULT NULL COMMENT '道具描述',
    prop_type   VARCHAR(50)   DEFAULT NULL COMMENT '道具类型',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ep_scene (scene_id),
    INDEX idx_ep_script (script_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 10. storyboard-service tables (Python — 分镜生成)
-- ============================================================

CREATE TABLE IF NOT EXISTS storyboard_tasks (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    task_id     VARCHAR(64)   NOT NULL COMMENT '任务UUID',
    script_id   BIGINT        DEFAULT NULL COMMENT '关联剧本ID',
    status      VARCHAR(20)   NOT NULL DEFAULT 'pending',
    progress    INT           DEFAULT 0,
    result_json LONGTEXT      DEFAULT NULL COMMENT '分镜结果 JSON',
    error       TEXT          DEFAULT NULL,
    user_id     VARCHAR(64)   DEFAULT NULL,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_st_task_id (task_id),
    INDEX idx_st_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS overview_configs (
    user_id            VARCHAR(64) PRIMARY KEY,
    video_ratio        INT         DEFAULT 0,
    creation_mode      INT         DEFAULT 0,
    style_reference    INT         DEFAULT 0,
    created_at         DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
