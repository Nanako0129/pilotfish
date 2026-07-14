export function selectCommittedUsage(state) {
  const latestCommitted = [...state.messages]
    .reverse()
    .find((message) => message.committed);

  return latestCommitted?.usage ?? null;
}
