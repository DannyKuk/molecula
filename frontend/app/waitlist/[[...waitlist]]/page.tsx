import { Waitlist } from "@clerk/nextjs";

import { LoginPage } from "@/components/login-page";

export default function WaitlistPage() {
  return (
    <LoginPage>
      <Waitlist />
    </LoginPage>
  );
}
