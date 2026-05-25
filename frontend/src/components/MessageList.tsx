import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Message } from '../types/chat';

interface MessageListProps {
  messages: Message[];
  loading: boolean;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, loading }) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  return (
    <div className="message-list">
      {messages.length === 0 ? (
        <div className="chat-empty-state">
          <span className="empty-icon">AI</span>
          <h3>Ask a question and watch the pipeline work</h3>
          <p>
            The chatbot keeps short context, the SDK captures inference metadata, and the ingestion
            API stores logs for the dashboard.
          </p>
          <div className="prompt-suggestions">
            <span>Try:</span>
            <code>Summarize vector databases in 4 bullets</code>
            <code>Write a test plan for an API wrapper</code>
          </div>
        </div>
      ) : (
        messages.map((message) => (
          <article key={message.id} className={`message-row ${message.role}`}>
            <div className="message-avatar">{message.role === 'user' ? 'You' : 'LLM'}</div>
            <div className="message-bubble">
              <div className="message-meta">
                <strong>{message.role === 'user' ? 'You' : 'Assistant'}</strong>
                <span>{new Date(message.created_at).toLocaleTimeString()}</span>
              </div>
              <div className="message-content">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            </div>
          </article>
        ))
      )}

      {loading && (
        <article className="message-row assistant">
          <div className="message-avatar">LLM</div>
          <div className="message-bubble typing">
            <span />
            <span />
            <span />
          </div>
        </article>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};
