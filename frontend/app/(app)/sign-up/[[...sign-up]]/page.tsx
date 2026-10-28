import { SignUp } from "@clerk/nextjs";

import { LoginPage } from "@/components/login-page";

export default function SignUpPage() {
  return (
    <LoginPage>
      <SignUp />
    </LoginPage>
  );
}
