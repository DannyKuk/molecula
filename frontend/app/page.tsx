import { Suspense } from "react";

import { Chat } from "@/components/chat";

import { LinkedChat } from "./linked-chat";

export default function Home() {
  return (
    <Suspense fallback={<Chat />}>
      <LinkedChat />
    </Suspense>
  );
}
