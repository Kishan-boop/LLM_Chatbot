/**
 * API client for chatbot backend.
 * Includes CSRF token handling and Zod validation.
 */
import { z } from 'zod';
import type {
  ChatRequest,
  ChatResponse,
  ConversationHistory,
  ConversationMetadata,
  InferenceLog,
  MetricsSummary,
} from '../types/chat';

// Zod schemas for runtime validation
const ChatResponseSchema = z.object({
  conversation_id: z.string(),
  message: z.string(),
  created_at: z.string(),
  model: z.string(),
});

const ConversationMetadataSchema = z.object({
  id: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  message_count: z.number(),
  model_name: z.string(),
});

const ConversationsListSchema = z.array(ConversationMetadataSchema);

const MessageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant', 'system']),
  content: z.string(),
  created_at: z.string(),
  token_count: z.number(),
});

const ConversationHistorySchema = z.object({
  conversation: ConversationMetadataSchema,
  messages: z.array(MessageSchema),
});

const MetricsSummarySchema = z.object({
  total_requests: z.number(),
  error_count: z.number(),
  error_rate: z.number(),
  avg_latency_ms: z.number(),
  total_tokens: z.number(),
  throughput_per_minute: z.number(),
  providers: z.array(z.object({
    provider: z.string(),
    model: z.string(),
    requests: z.number(),
    avg_latency_ms: z.number(),
    tokens: z.number(),
  })),
});

const InferenceLogSchema = z.object({
  id: z.string(),
  conversation_id: z.string(),
  message_id: z.string().nullable(),
  provider: z.string(),
  model: z.string(),
  latency_ms: z.number().nullable(),
  prompt_tokens: z.number(),
  completion_tokens: z.number(),
  total_tokens: z.number(),
  status: z.enum(['success', 'error', 'timeout']),
  error_message: z.string().nullable(),
  input_preview: z.string().nullable(),
  output_preview: z.string().nullable(),
  created_at: z.string(),
});

const InferenceLogsSchema = z.array(InferenceLogSchema);

/**
 * Get CSRF token from cookie.
 * Called before making state-changing requests.
 */
export function getCsrfToken(): string | null {
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'csrf_token') {
      return value;
    }
  }
  return null;
}

/**
 * Fetch CSRF token from server.
 * Makes a GET request to trigger cookie setting.
 */
export async function fetchCsrfToken(): Promise<void> {
  try {
    await fetch('/health', {
      method: 'GET',
      credentials: 'include',
    });
  } catch (error) {
    console.error('Failed to fetch CSRF token:', error);
  }
}

/**
 * Send a chat message to the backend.
 * Validates response with Zod schema.
 */
export async function sendMessage(
  conversationId: string | null,
  message: string,
  signal?: AbortSignal
): Promise<ChatResponse> {
  // Validate input length
  if (message.length === 0 || message.length > 4000) {
    throw new Error('Message must be between 1 and 4000 characters');
  }

  const csrfToken = getCsrfToken();
  if (!csrfToken) {
    throw new Error('CSRF token not found. Please refresh the page.');
  }

  const requestBody: ChatRequest = {
    message,
  };

  if (conversationId) {
    requestBody.conversation_id = conversationId;
  }

  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    credentials: 'include',
    signal,
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}`);
  }

  const data = await response.json();

  // Validate response with Zod
  const validatedData = ChatResponseSchema.parse(data);

  return validatedData;
}

export async function streamMessage(
  conversationId: string | null,
  message: string,
  onStart: (data: { conversation_id: string; model: string }) => void,
  onToken: (token: string) => void,
  signal?: AbortSignal
): Promise<ChatResponse> {
  if (message.length === 0 || message.length > 4000) {
    throw new Error('Message must be between 1 and 4000 characters');
  }

  const csrfToken = getCsrfToken();
  if (!csrfToken) {
    throw new Error('CSRF token not found. Please refresh the page.');
  }

  const requestBody: ChatRequest = { message };
  if (conversationId) {
    requestBody.conversation_id = conversationId;
  }

  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    credentials: 'include',
    signal,
    body: JSON.stringify(requestBody),
  });

  if (!response.ok || !response.body) {
    if (response.status === 404) {
      const fallbackResponse = await sendMessage(conversationId, message, signal);
      onStart({
        conversation_id: fallbackResponse.conversation_id,
        model: fallbackResponse.model,
      });
      onToken(fallbackResponse.message);
      return fallbackResponse;
    }

    const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResponse: ChatResponse | null = null;

  const handleEvent = (rawEvent: string) => {
    const eventLine = rawEvent.split('\n').find((line) => line.startsWith('event: '));
    const dataLine = rawEvent.split('\n').find((line) => line.startsWith('data: '));
    if (!eventLine || !dataLine) {
      return;
    }

    const eventName = eventLine.slice('event: '.length).trim();
    const payload = JSON.parse(dataLine.slice('data: '.length));

    if (eventName === 'start') {
      onStart(payload);
    } else if (eventName === 'token') {
      onToken(payload.token);
    } else if (eventName === 'done') {
      finalResponse = ChatResponseSchema.parse(payload);
    } else if (eventName === 'error') {
      throw new Error(payload.error || 'Streaming response failed');
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() || '';
    for (const event of events) {
      if (event.trim()) {
        handleEvent(event);
      }
    }
  }

  if (buffer.trim()) {
    handleEvent(buffer);
  }

  if (!finalResponse) {
    throw new Error('Streaming response ended without completion metadata');
  }

  return finalResponse;
}

/**
 * Get list of recent conversations.
 * Validates response with Zod schema.
 */
export async function getConversations(): Promise<ConversationMetadata[]> {
  const response = await fetch('/api/conversations', {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch conversations: HTTP ${response.status}`);
  }

  const data = await response.json();

  // Validate response with Zod
  const validatedData = ConversationsListSchema.parse(data);

  return validatedData;
}

export async function getConversationHistory(conversationId: string): Promise<ConversationHistory> {
  const response = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch conversation: HTTP ${response.status}`);
  }

  return ConversationHistorySchema.parse(await response.json());
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const csrfToken = getCsrfToken();
  if (!csrfToken) {
    throw new Error('CSRF token not found. Please refresh the page.');
  }

  const response = await fetch(`/api/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: {
      'X-CSRF-Token': csrfToken,
    },
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to delete conversation: HTTP ${response.status}`);
  }
}

export async function getMetrics(): Promise<MetricsSummary> {
  const response = await fetch('/ingestion-api/metrics', {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch metrics: HTTP ${response.status}`);
  }

  return MetricsSummarySchema.parse(await response.json());
}

export async function getInferenceLogs(limit = 8): Promise<InferenceLog[]> {
  const response = await fetch(`/ingestion-api/logs?limit=${limit}`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch inference logs: HTTP ${response.status}`);
  }

  return InferenceLogsSchema.parse(await response.json());
}
