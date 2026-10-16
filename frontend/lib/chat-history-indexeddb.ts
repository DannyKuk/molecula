import { type ChatHistory, type Conversation, summaryOf } from "./chat-history";

const DATABASE = "molecula";
const VERSION = 2;
const CONVERSATIONS = "conversations";
const BOOKMARKS = "bookmarks";
const BOOKMARK_ORDER = "order";

/**
 * The conversations and the bookmarks in the browser's IndexedDB. The database opens on the first
 * call, so making one costs nothing on the server; without IndexedDB, or when the browser refuses
 * it, every call rejects.
 */
export function indexedDbHistory(): ChatHistory {
  let database: Promise<IDBDatabase> | undefined;

  function request<T>(
    storeName: string,
    mode: IDBTransactionMode,
    use: (store: IDBObjectStore) => IDBRequest<T>,
  ): Promise<T> {
    database ??= openDatabase();
    return database.then(
      (db) =>
        new Promise<T>((resolve, reject) => {
          const transaction = db.transaction(storeName, mode);
          const pending = use(transaction.objectStore(storeName));
          transaction.oncomplete = () => resolve(pending.result);
          transaction.onerror = () => reject(transaction.error);
          transaction.onabort = () => reject(transaction.error);
        }),
    );
  }

  return {
    list: async () =>
      (await request<Conversation[]>(CONVERSATIONS, "readonly", (store) => store.getAll())).map(
        summaryOf,
      ),
    get: (id) =>
      request<Conversation | undefined>(CONVERSATIONS, "readonly", (store) => store.get(id)),
    put: async (conversation) => {
      await request(CONVERSATIONS, "readwrite", (store) => store.put(conversation));
    },
    delete: async (id) => {
      await request(CONVERSATIONS, "readwrite", (store) => store.delete(id));
    },
    bookmarks: async () =>
      (await request<string[] | undefined>(BOOKMARKS, "readonly", (store) =>
        store.get(BOOKMARK_ORDER),
      )) ?? [],
    putBookmarks: async (ids) => {
      await request(BOOKMARKS, "readwrite", (store) => store.put(ids, BOOKMARK_ORDER));
    },
  };
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    // Throws when the browser has no IndexedDB; the promise turns that into a rejection.
    const opening = globalThis.indexedDB.open(DATABASE, VERSION);
    // Version 1 kept only the conversations, so an upgrade adds just the stores that are missing.
    opening.onupgradeneeded = () => {
      const db = opening.result;
      if (!db.objectStoreNames.contains(CONVERSATIONS)) {
        db.createObjectStore(CONVERSATIONS, { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains(BOOKMARKS)) db.createObjectStore(BOOKMARKS);
    };
    opening.onsuccess = () => {
      const db = opening.result;
      // A tab with newer code asks to upgrade; closing here lets it, instead of leaving it blocked.
      db.onversionchange = () => db.close();
      resolve(db);
    };
    opening.onerror = () => reject(opening.error);
  });
}
