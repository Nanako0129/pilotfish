export function createAssistantMessage(id, usage = { inputTokens: 0, outputTokens: 0 }) {
  return {
    id,
    type: "assistant",
    committed: false,
    usage: { ...usage },
  };
}

export function commitAssistantMessage(message, usage) {
  message.committed = true;
  message.usage = { ...usage };

  return {
    type: "message_delta",
    messageId: message.id,
    message,
  };
}
