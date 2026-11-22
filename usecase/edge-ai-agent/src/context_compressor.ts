/**
 * Lensetek Edge Context Compressor (PM-08: Anti Context-Overflow 4K SLM Protection)
 *
 * Prevents out-of-memory and context degradation on 4,096-token edge models
 * by dynamically digesting older episodic tool observations and enforcing chunk limits.
 */

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content?: string | null;
  tool_calls?: any[];
  tool_call_id?: string;
  name?: string;
}

/**
 * Compresses conversation history to stay strictly within edge SLM 4K token budgets.
 *
 * @param messages Full raw message history
 * @param maxRecentToolTurns Number of recent tool observations to keep uncompressed (default: 3)
 * @param maxChunkChars Maximum characters for raw context chunks (~300 tokens, default: 1100)
 * @returns Compressed message array ready for edge inference
 */
export function compressEpisodicHistory(
  messages: ChatMessage[],
  maxRecentToolTurns: number = 3,
  maxChunkChars: number = 1100
): ChatMessage[] {
  if (!messages || messages.length === 0) return [];

  // Identify index of the last user turn
  let lastUserIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user') {
      lastUserIdx = i;
      break;
    }
  }

  // Count backwards to find indices of recent tool messages that can stay full
  const toolIndices: number[] = [];
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role === 'tool') {
      toolIndices.push(i);
    }
  }

  const uncompressedToolSet = new Set<number>(
    toolIndices.slice(-maxRecentToolTurns)
  );

  return messages.map((msg, idx) => {
    // 1. Keep system message intact
    if (msg.role === 'system') {
      return { ...msg };
    }

    // 2. Keep the latest user message intact
    if (idx === lastUserIdx) {
      return { ...msg };
    }

    // 3. Handle tool observations
    if (msg.role === 'tool') {
      // If within recent turns, apply maxChunkChars ceiling only
      if (uncompressedToolSet.has(idx)) {
        if (msg.content && msg.content.length > maxChunkChars) {
          return {
            ...msg,
            content:
              msg.content.substring(0, maxChunkChars) +
              '\n... [TRUNCATED FOR 4K CONTEXT SLM MEMORY]',
          };
        }
        return { ...msg };
      }

      // Older tool observation -> Digest into single compact 1-line string (< 45 tokens)
      const toolName = msg.name || 'tool';
      let summaryText = 'data processed';
      if (msg.content) {
        // Strip newlines and extract clean gist
        const cleanContent = msg.content.replace(/\s+/g, ' ').trim();
        summaryText = cleanContent.length > 80
          ? cleanContent.substring(0, 77) + '...'
          : cleanContent;
      }

      return {
        ...msg,
        content: `[DIGEST tool=${toolName} status=ok summary="${summaryText}"]`,
      };
    }

    // 4. Handle assistant message with tool calls or previous responses
    if (msg.role === 'assistant') {
      // If older text content is very verbose, apply gentle cap
      if (msg.content && msg.content.length > maxChunkChars * 2) {
        return {
          ...msg,
          content:
            msg.content.substring(0, maxChunkChars * 2) +
            '\n... [TRUNCATED PREVIOUS RESPONSE]',
        };
      }
      return { ...msg };
    }

    // 5. Handle older user messages
    if (msg.role === 'user' && msg.content && msg.content.length > maxChunkChars) {
      return {
        ...msg,
        content:
          msg.content.substring(0, maxChunkChars) +
          '\n... [USER PROMPT TRUNCATED]',
      };
    }

    return { ...msg };
  });
}
