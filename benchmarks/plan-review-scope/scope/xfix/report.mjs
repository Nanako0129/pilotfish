import { formatUser } from "./format.mjs";
import { decodeUser } from "./store.mjs";

export function reportLine(raw) {
  return `user: ${formatUser(decodeUser(raw))}`;
}
