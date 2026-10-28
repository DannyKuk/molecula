import { SignIn } from "@clerk/nextjs";

import { LoginPage } from "@/components/login-page";

export default function SignInPage() {
  return (
    <LoginPage>
      <SignIn />
    </LoginPage>
  );
}
