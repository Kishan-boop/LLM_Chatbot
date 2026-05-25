import React, { useState } from 'react';
import { z } from 'zod';

interface MessageInputProps {
  onSendMessage: (message: string) => Promise<void>;
  onCancel: () => void;
  disabled: boolean;
}

const MessageSchema = z.string().trim().min(1).max(4000);

export const MessageInput: React.FC<MessageInputProps> = ({ onSendMessage, onCancel, disabled }) => {
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const validation = MessageSchema.safeParse(input);
    if (!validation.success) {
      setError('Enter a message between 1 and 4000 characters.');
      return;
    }

    setError(null);
    try {
      await onSendMessage(validation.data);
      setInput('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message.');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      {error && <div className="input-error">{error}</div>}
      <div className="composer-row">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message the model..."
          disabled={disabled}
          rows={3}
        />
        <div className="composer-actions">
          {disabled ? (
            <button type="button" className="secondary-action" onClick={onCancel}>
              Cancel
            </button>
          ) : null}
          <button type="submit" className="send-action" disabled={disabled || !input.trim()}>
            {disabled ? 'Running' : 'Send'}
          </button>
        </div>
      </div>
      <div className="composer-footer">
        <span>Enter sends · Shift+Enter adds a line</span>
        <span>{input.length}/4000</span>
      </div>
    </form>
  );
};
