import {
  commitAssistantMessage,
  createAssistantMessage,
} from "./messages.js";
import { reduceSession } from "./reducer.js";
import { selectCommittedUsage } from "./statusline.js";

export class Session {
  constructor() {
    this.state = { messages: [] };
    this.canonicalMessages = new Map();
  }

  startAssistant(id) {
    const message = createAssistantMessage(id);
    this.canonicalMessages.set(id, message);
    this.state = reduceSession(this.state, { type: "assistant", message });
  }

  finishAssistant(id, usage) {
    const message = this.canonicalMessages.get(id);
    this.state = reduceSession(
      this.state,
      commitAssistantMessage(message, usage),
    );
  }

  committedUsage() {
    return selectCommittedUsage(this.state);
  }
}
