-- LLM Inference Logger Database Schema
-- SQLite 3.x compatible

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Conversations table
-- Stores chat conversation metadata
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,  -- UUID v4
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,  -- Optional user identifier
    context_window_size INTEGER NOT NULL DEFAULT 10,  -- Max messages to keep in context
    model_name TEXT NOT NULL DEFAULT 'llama-3.1-70b-versatile'
);

-- Index for querying recent conversations
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

-- Messages table
-- Stores individual chat messages
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,  -- UUID v4
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    token_count INTEGER DEFAULT 0,  -- Approximate token count
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Index for efficient conversation history retrieval
CREATE INDEX IF NOT EXISTS idx_messages_conversation_time ON messages(conversation_id, created_at);

-- Inference logs table
-- Stores LLM API call metadata and performance metrics
CREATE TABLE IF NOT EXISTS inference_logs (
    id TEXT PRIMARY KEY,  -- UUID v4
    conversation_id TEXT NOT NULL,
    message_id TEXT,  -- Can be NULL if inference failed before message creation
    provider TEXT NOT NULL,  -- 'groq', 'openai', etc.
    model TEXT NOT NULL,  -- e.g., 'llama-3.1-70b-versatile'
    request_timestamp TIMESTAMP NOT NULL,
    response_timestamp TIMESTAMP,  -- NULL if request failed/timeout
    latency_ms INTEGER,  -- End-to-end latency in milliseconds
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('success', 'error', 'timeout')),
    error_message TEXT,  -- Error details if status != 'success'
    input_preview TEXT,  -- First 200 chars of prompt for debugging
    output_preview TEXT,  -- First 200 chars of response
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL
);

-- Indexes for analytics and monitoring queries
CREATE INDEX IF NOT EXISTS idx_inference_logs_conversation ON inference_logs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_inference_logs_time_status ON inference_logs(created_at DESC, status);
CREATE INDEX IF NOT EXISTS idx_inference_logs_provider_model ON inference_logs(provider, model);

-- Trigger to update conversations.updated_at when new message is added
CREATE TRIGGER IF NOT EXISTS update_conversation_timestamp
AFTER INSERT ON messages
BEGIN
    UPDATE conversations
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.conversation_id;
END;
