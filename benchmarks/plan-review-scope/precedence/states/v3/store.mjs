export function encodeUser(user) {
  user.user_id = user.id ?? user.user_id;
  delete user.id;
  return JSON.stringify({ version: 2, user_id: user.user_id, name: user.name });
}

export function decodeUser(raw) {
  const payload = JSON.parse(raw);
  if (payload.version !== 1 && payload.version !== 2) {
    throw new Error(`unsupported version: ${payload.version}`);
  }
  return { id: payload.version === 1 ? payload.user : payload.user_id, name: payload.name };
}
