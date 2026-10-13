// The same limits as the backend's chat request in backend/src/molecula/schemas/chat.py.

/** The most messages one request may carry; a longer conversation sends its latest ones. */
export const MAX_MESSAGES = 10;

/** The most characters a question may have. */
export const MAX_MESSAGE_LENGTH = 4000;

/** The most characters an earlier answer may have when it is sent back. */
export const MAX_ANSWER_LENGTH = 8000;
