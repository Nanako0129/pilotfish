const written = [];

export function encodeUser(user) {
  const raw = JSON.stringify({ version: 2, user_id: user.id, name: user.name });
  written.push({ at: Date.now(), user, raw });
  return raw;
}

export function decodeUser(raw) {
  const payload = JSON.parse(raw);
  if (payload.version !== 1 && payload.version !== 2) {
    throw new Error(`unsupported version: ${payload.version}`);
  }
  return { id: payload.version === 1 ? payload.user : payload.user_id, name: payload.name };
}
