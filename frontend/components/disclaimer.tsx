const DAILYMED_URL = "https://dailymed.nlm.nih.gov/";

/** The reminder that answers come from an AI and where to check them, shown on every page. */
export function Disclaimer() {
  return (
    <p className="text-sm text-zinc-600 dark:text-zinc-400">
      Molecula is an AI assistant and can make mistakes. It is not medical advice. Check the
      official label on{" "}
      <a
        href={DAILYMED_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline underline-offset-4"
      >
        DailyMed
      </a>{" "}
      and ask a pharmacist or doctor before acting on anything here.
    </p>
  );
}
