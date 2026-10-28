"use client";

import { cn } from "cn";
import Link from "next/link";
import { type ReactNode, useEffect, useRef } from "react";

import { LOGIN_ON } from "@/lib/login";
import { useMessages } from "@/lib/messages";
import { useMediaQuery } from "@/lib/use-media-query";

import { Brand } from "../brand-mark";
import { LanguageSwitch } from "../language-switch";
import { LegalLinks } from "../legal-links";
import { ThemeSwitch } from "../theme-switch";
import { LandingScreen } from "./landing-screen";
import { QuestionTrace } from "./question-trace";

const REPO_URL = "https://github.com/DannyKuk/molecula";
const ARCHITECTURE_URL = `${REPO_URL}/blob/main/docs/architecture.md`;
const AUTHOR_URL = "https://dkwebsite.de";

// From the built store (133 compounds, 73 complex files) and the last full safety eval of the
// cloud setup (`docs/evals/input-check-larger-set-2026-10-19.md`).
const NUMBERS = [
  { value: "133", key: "drugs" },
  { value: "73", key: "complexes" },
  { value: "64/64", key: "safety" },
  { value: "0", key: "offline" },
] as const;

const STACK = [
  "Python · FastAPI",
  "LangChain agent, 6 tools",
  "bge-m3 label search",
  "SQLite store",
  "MCP server",
  "Next.js 16",
  "3Dmol.js",
  "gpt-oss-20b offline · cloud model online",
  "Docker",
];

const BUTTON =
  "inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2";
const ON_SCREEN =
  "border border-screen-dim/50 text-screen-ink hover:bg-screen-ink/8 focus-visible:outline-screen-ink";

/** What a visitor who isn't signed in sees at `/` (#455): the app's 3D view live at the top, one
 * recorded question followed through its steps, the numbers, the launch video and who built it. */
export function LandingPage() {
  const t = useMessages();
  const l = t.landing;
  return (
    <div className="flex flex-1 flex-col bg-page">
      <LandingScreen nav={<Nav />}>
        <h1 className="text-[clamp(36px,5.2vw,60px)] leading-[1.04] font-semibold tracking-[-0.03em] text-screen-ink">
          {l.headline} <span className="text-signal">{l.accent}</span>
        </h1>
        <p className="mt-4 mb-7 max-w-[560px] text-lg text-screen-dim">{l.lead}</p>
        <div className="flex flex-wrap gap-2.5">
          {/* Without the login the chat is open, as in development, so the page leads straight to it. */}
          <Link
            href={LOGIN_ON ? "/waitlist" : "/"}
            className={cn(
              BUTTON,
              "bg-signal text-white hover:brightness-95 focus-visible:outline-signal",
            )}
          >
            {LOGIN_ON ? l.requestAccess : l.openChat}
          </Link>
          <a href="#how" className={cn(BUTTON, ON_SCREEN)}>
            {l.nav.how} ↓
          </a>
        </div>
      </LandingScreen>

      <main className="mx-auto w-full max-w-[1160px] px-4 md:px-6">
        <section id="how" className="scroll-mt-6 py-16 md:py-22">
          <QuestionTrace />
          <dl className="mt-16 grid grid-cols-2 border-y border-rule lg:grid-cols-4">
            {NUMBERS.map(({ value, key }, index) => (
              <div
                key={key}
                className={cn(
                  "flex flex-col-reverse py-5 pr-5",
                  index % 2 === 1 && "border-l border-rule pl-5",
                  index >= 2 && "border-t border-rule lg:border-t-0",
                  index === 2 && "lg:border-l lg:pl-5",
                )}
              >
                <dt className="text-sm text-ink-2">{l.numbers[key]}</dt>
                <dd className="font-mono text-3xl font-medium tracking-tighter">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="border-t border-rule py-16 md:py-22">
          <LaunchVideo />
        </section>

        <section className="border-t border-rule py-12">
          <h2 className="mb-3 font-mono text-xs text-ink-3">{l.builtWith}</h2>
          <ul className="flex flex-wrap gap-x-5 gap-y-2 font-mono text-[13px] text-ink-2">
            {STACK.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="mx-auto w-full max-w-[1160px] px-4 md:px-6">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4 border-t border-rule py-8 text-sm text-ink-3">
          <p>
            {l.builtBy} <FooterLink href={AUTHOR_URL}>Danny Kukic</FooterLink> ·{" "}
            <FooterLink href={REPO_URL}>GitHub</FooterLink> ·{" "}
            <FooterLink href={ARCHITECTURE_URL}>{l.architecture}</FooterLink>
          </p>
          <div className="flex items-center gap-2">
            <LanguageSwitch />
            <ThemeSwitch />
          </div>
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 pb-12">
          <p className="text-sm text-ink-3">{l.notAdvice}</p>
          <LegalLinks className="text-sm" />
        </div>
      </footer>
    </div>
  );
}

function Nav() {
  const l = useMessages().landing;
  return (
    <nav className="flex h-16 items-center justify-between gap-4">
      <Link href="/" className="text-[17px] text-screen-ink">
        <Brand />
      </Link>
      <div className="flex items-center gap-5 text-sm text-screen-dim">
        <a href="#how" className="hidden hover:text-screen-ink sm:inline">
          {l.nav.how}
        </a>
        <a href={REPO_URL} className="hidden hover:text-screen-ink sm:inline">
          {l.nav.code}
        </a>
        {LOGIN_ON && (
          <Link href="/sign-in" className={cn(BUTTON, ON_SCREEN)}>
            {l.nav.signIn}
          </Link>
        )}
      </div>
    </nav>
  );
}

function FooterLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} className="text-ink-2 underline-offset-4 hover:text-ink hover:underline">
      {children}
    </a>
  );
}

/** The launch video as a figure, playing muted while it is on screen; with reduced motion it
 * waits for the play button. */
function LaunchVideo() {
  const v = useMessages().landing.video;
  const video = useRef<HTMLVideoElement>(null);
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

  useEffect(() => {
    const element = video.current!;
    if (reduceMotion) return;
    const visible = new IntersectionObserver(
      ([entry]) => {
        // play() rejects when the browser blocks it; the poster stays and the controls still work.
        if (entry.isIntersecting) element.play().catch(() => {});
        else element.pause();
      },
      { threshold: 0.25 },
    );
    visible.observe(element);
    return () => visible.disconnect();
  }, [reduceMotion]);

  return (
    <figure>
      <video
        ref={video}
        aria-label={v.label}
        src="/landing/launch.mp4"
        poster="/landing/launch-poster.jpg"
        muted
        loop
        playsInline
        preload="none"
        controls={reduceMotion}
        className="aspect-video w-full rounded-[10px] bg-screen"
      />
      <figcaption className="flex flex-wrap justify-between gap-x-4 gap-y-1 pt-3 text-sm text-ink-2">
        <span>{v.caption}</span>
        <span className="font-mono text-xs text-ink-3">{v.meta}</span>
      </figcaption>
    </figure>
  );
}
