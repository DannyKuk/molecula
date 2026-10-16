import { type ChatHistory, type Conversation, summaryOf } from "./chat-history";

const DATABASE = "molecula";
const VERSION = 1;
const CONVERSATIONS = "conversations";

/**
 * The conversations in the browser's IndexedDB. The database opens on the first call, so making
 * one costs nothing on the server; without IndexedDB, or when the browser refuses it, every call
 * rejects.
 */
export function indexedDbHistory(): ChatHistory {
  let database: Promise<IDBDatabase> | undefined;

  function request<T>(
    mode: IDBTransactionMode,
    use: (store: IDBObjectStore) => IDBRequest<T>,
  ): Promise<T> {
    database ??= openDatabase();
    return database.then(
      (db) =>
        new Promise<T>((resolve, reject) => {
          const transaction = db.transaction(CONVERSATIONS, mode);
          const pending = use(transaction.objectStore(CONVERSATIONS));
          transaction.oncomplete = () => resolve(pending.result);
          transaction.onerror = () => reject(transaction.error);
          transaction.onabort = () => reject(transaction.error);
        }),
    );
  }

  return {
    list: async () =>
      (await request<Conversation[]>("readonly", (store) => store.getAll())).map(summaryOf),
    get: (id) => request<Conversation | undefined>("readonly", (store) => store.get(id)),
    put: async (conversation) => {
      await request("readwrite", (store) => store.put(conversation));
    },
    delete: async (id) => {
      await request("readwrite", (store) => store.delete(id));
    },
  };
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    // Throws when the browser has no IndexedDB; the promise turns that into a rejection.
    const opening = globalThis.indexedDB.open(DATABASE, VERSION);
    opening.onupgradeneeded = () =>
      opening.result.createObjectStore(CONVERSATIONS, { keyPath: "id" });
    opening.onsuccess = () => resolve(opening.result);
    opening.onerror = () => reject(opening.error);
  });
}
