export function reduceSession(state, event) {
  if (event.type === "assistant") {
    return {
      ...state,
      messages: [
        ...state.messages,
        {
          ...event.message,
          usage: { ...event.message.usage },
        },
      ],
    };
  }

  if (event.type === "message_delta") {
    // The stream mutates the canonical message before this event arrives.
    // The status-line state intentionally owns clones, not canonical wrappers.
    return state;
  }

  return state;
}
