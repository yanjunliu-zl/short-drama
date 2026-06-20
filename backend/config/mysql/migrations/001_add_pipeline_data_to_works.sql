-- Migration: Add pipeline_data column to works table
-- Purpose: Store full pipeline state as JSON snapshot for persistence across user sessions
-- Run: docker exec -i shortdrama-mysql mysql -uadmin -padmin123 shortdrama < 001_add_pipeline_data_to_works.sql

ALTER TABLE works ADD COLUMN IF NOT EXISTS pipeline_data LONGTEXT DEFAULT NULL COMMENT 'JSON snapshot of full pipeline state (script, scenes, characters, props, storyboard, video results, final cut)';
