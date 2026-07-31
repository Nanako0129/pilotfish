export function encodeUser(user) {
  return JSON.stringify({ version: 1, user: user.id, name: user.name });
}

export function decodeUser(raw) {
  const payload = JSON.parse(raw);
  if (payload.version !== 1) {
    throw new Error(`unsupported version: ${payload.version}`);
  }
  return { id: payload.user, name: payload.name };
}
