"use client";

import { UserButton, useAuth } from "@clerk/nextjs";
import { useEffect } from "react";

import { LOGIN_ON, setGetToken } from "@/lib/login";

/** Hands Clerk's getToken to lib/login, so the backend requests carry the session token. */
export function LoginToken() {
  const { getToken } = useAuth();
  useEffect(() => setGetToken(getToken), [getToken]);
  return null;
}

/** The signed-in user's avatar: their profile and Sign out. Nothing while the login is off. */
export function UserMenu() {
  if (!LOGIN_ON) return null;
  return <UserButton />;
}
