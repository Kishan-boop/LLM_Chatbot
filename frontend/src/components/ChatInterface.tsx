import React, { useEffect, useMemo, useRef, useState } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import {
  deleteConversation,
  fetchCsrfToken,
  getConversationHistory,
  getConversations,
  getInferenceLogs,
  getMetrics,
  streamMessage,
} from '../api/client';
import type { ConversationMetadata, InferenceLog, Message, MetricsSummary } from '../types/chat';

type HealthState = 'online' | 'degraded' | 'checking';

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationMetadata[]>([]);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [logs, setLogs] = useState<InferenceLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthState>('checking');
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchCsrfToken();
    refreshAll();
    const timer = window.setInterval(refreshTelemetry, 4000);
    return () => window.clearInterval(timer);
  }, []);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === conversationId),
    [conversationId, conversations]
  );

  const refreshAll = async () => {
    await Promise.all([refreshConversations(), refreshTelemetry()]);
  };

  const refreshConversations = async () => {
    try {
      setConversations(await getConversations());
      setHealth('online');
    } catch (err) {
      console.warn('Failed to refresh conversations', err);
      setHealth('degraded');
    }
  };

  const refreshTelemetry = async () => {
    try {
      const [nextMetrics, nextLogs] = await Promise.all([getMetrics(), getInferenceLogs(8)]);
      setMetrics(nextMetrics);
      setLogs(nextLogs);
      setHealth('online');
    } catch (err) {
      console.warn('Failed to refresh telemetry', err);
      setHealth('degraded');
    }
  };

  const handleSendMessage = async (messageText: string) => {
    setLoading(true);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: messageText,
      created_at: new Date().toISOString(),
      token_count: 0,
    };

    setMessages((prev) => [...prev, tempUserMessage]);

    try {
      let assistantMessageId = `assistant-${Date.now()}`;

      const response = await streamMessage(
        conversationId,
        messageText,
        (start) => {
          if (!conversationId) {
            setConversationId(start.conversation_id);
          }
          assistantMessageId = `${start.conversation_id}-${Date.now()}`;
          setMessages((prev) => [
            ...prev,
            {
              id: assistantMessageId,
              role: 'assistant',
              content: '',
              created_at: new Date().toISOString(),
              token_count: 0,
            },
          ]);
        },
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId ? { ...msg, content: `${msg.content}${token}` } : msg
            )
          );
        },
        controller.signal
      );

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, content: response.message, created_at: response.created_at }
            : msg
        )
      );

      await refreshAll();
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError('Conversation request cancelled.');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to send message');
      }
      setMessages((prev) => prev.filter((msg) => msg.id !== tempUserMessage.id));
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  };

  const handleCancel = () => {
    abortRef.current?.abort();
  };

  const handleNewConversation = () => {
    handleCancel();
    setConversationId(null);
    setMessages([]);
    setError(null);
  };

  const handleResumeConversation = async (id: string) => {
    handleCancel();
    setError(null);
    try {
      const history = await getConversationHistory(id);
      setConversationId(history.conversation.id);
      setMessages(history.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversation');
    }
  };

  const handleDeleteConversation = async (id: string) => {
    handleCancel();
    setError(null);
    try {
      await deleteConversation(id);
      if (conversationId === id) {
        setConversationId(null);
        setMessages([]);
      }
      await refreshConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete conversation');
    }
  };

  return (
    <div className="app-shell">
      <aside className="conversation-rail">
        <div className="brand">
          <div>
            <p className="eyebrow">LLM observability</p>
            <h1>Inference Logger</h1>
          </div>
          <span className={`health-dot ${health}`} title={`Services ${health}`} />
        </div>

        <button className="primary-action" onClick={handleNewConversation}>
          New conversation
        </button>

        <div className="section-heading">
          <span>Conversations</span>
          <span>{conversations.length}</span>
        </div>

        <div className="conversation-list">
          {conversations.length === 0 ? (
            <div className="empty-panel">
              <strong>No conversations yet</strong>
              <span>Send a message to create the first logged session.</span>
            </div>
          ) : (
            conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`conversation-row ${conversation.id === conversationId ? 'active' : ''}`}
              >
                <button onClick={() => handleResumeConversation(conversation.id)}>
                  <strong>{conversation.id.slice(0, 12)}</strong>
                  <span>{conversation.message_count} messages</span>
                  <small>{formatDate(conversation.updated_at)}</small>
                </button>
                <button
                  className="danger-icon"
                  onClick={() => handleDeleteConversation(conversation.id)}
                  title="Delete conversation"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <main className="chat-workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Chatbot application</p>
            <h2>{conversationId ? `Session ${conversationId.slice(0, 10)}` : 'Start a logged LLM session'}</h2>
            <p className="header-copy">
              {activeConversation
                ? `${activeConversation.model_name} · ${activeConversation.message_count} stored messages`
                : 'Every response is captured by the SDK and ingested into the logging pipeline.'}
            </p>
          </div>
          <div className={`run-state ${loading ? 'running' : ''}`}>{loading ? 'Generating' : 'Ready'}</div>
        </header>

        {error && (
          <div className="error-banner">
            <strong>Action needed</strong>
            <span>{error}</span>
          </div>
        )}

        <section className="chat-panel">
          <MessageList messages={messages} loading={loading} />
          <MessageInput onSendMessage={handleSendMessage} onCancel={handleCancel} disabled={loading} />
        </section>
      </main>

      <aside className="telemetry-rail">
        <div className="section-heading">
          <span>Dashboards</span>
          <span>Live</span>
        </div>

        <div className="metric-stack">
          <Metric label="Requests" value={metrics?.total_requests ?? 0} />
          <Metric label="Req/min" value={metrics?.throughput_per_minute ?? 0} />
          <Metric label="Avg latency" value={`${metrics?.avg_latency_ms ?? 0} ms`} />
          <Metric label="Errors" value={metrics?.error_count ?? 0} tone={(metrics?.error_count ?? 0) > 0 ? 'bad' : 'good'} />
          <Metric label="Tokens" value={metrics?.total_tokens ?? 0} />
        </div>

        <div className="telemetry-card">
          <div className="card-title">Provider throughput</div>
          {metrics?.providers.length ? (
            metrics.providers.map((provider) => (
              <div key={`${provider.provider}-${provider.model}`} className="provider-line">
                <div>
                  <strong>{provider.provider}</strong>
                  <span>{provider.model}</span>
                </div>
                <small>{provider.requests} req</small>
              </div>
            ))
          ) : (
            <p className="muted">No provider calls yet.</p>
          )}
        </div>

        <div className="telemetry-card logs-card">
          <div className="card-title">Recent inference logs</div>
          {logs.length ? (
            logs.map((log) => (
              <div key={log.id} className="log-row">
                <div className="log-topline">
                  <span className={`status-badge ${log.status}`}>{log.status}</span>
                  <span>{log.latency_ms ?? 0} ms</span>
                  <span>{log.total_tokens} tokens</span>
                </div>
                <p>{log.input_preview || 'No input preview'}</p>
                <small>{formatDate(log.created_at)}</small>
              </div>
            ))
          ) : (
            <p className="muted">Send a message to see ingestion records.</p>
          )}
        </div>
      </aside>
    </div>
  );
};

const Metric = ({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string | number;
  tone?: 'neutral' | 'good' | 'bad';
}) => (
  <div className={`metric-card ${tone}`}>
    <span>{label}</span>
    <strong>{value}</strong>
  </div>
);

const formatDate = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value));
