import { formatUser } from "./format.mjs";

export function banner(user) {
  return `Welcome, ${formatUser(user)}!`;
}
