export function encodeUser(user) {
  return JSON.stringify({ version: 2, user_id: user.id, name: user.name });
}

export function decodeUser(raw) {
  const payload = JSON.parse(raw);
  if (payload.version !== 1 && payload.version !== 2) {
    throw new Error(`unsupported version: ${payload.version}`);
  }
  return { id: payload.version === 1 ? payload.user : payload.user_id, name: payload.name };
}
