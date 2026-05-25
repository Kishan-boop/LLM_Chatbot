/**
 * TypeScript type definitions for chat API.
 * These match the backend Pydantic models.
 */

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  token_count: number;
}

export interface ChatRequest {
  conversation_id?: string;
  message: string;
}

export interface ChatResponse {
  conversation_id: string;
  message: string;
  created_at: string;
  model: string;
}

export interface ConversationMetadata {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  model_name: string;
}

export interface ConversationHistory {
  conversation: ConversationMetadata;
  messages: Message[];
}

export interface MetricsSummary {
  total_requests: number;
  error_count: number;
  error_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  throughput_per_minute: number;
  providers: Array<{
    provider: string;
    model: string;
    requests: number;
    avg_latency_ms: number;
    tokens: number;
  }>;
}

export interface InferenceLog {
  id: string;
  conversation_id: string;
  message_id: string | null;
  provider: string;
  model: string;
  latency_ms: number | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  status: 'success' | 'error' | 'timeout';
  error_message: string | null;
  input_preview: string | null;
  output_preview: string | null;
  created_at: string;
}

export interface ApiError {
  error: string;
  detail?: string;
}
