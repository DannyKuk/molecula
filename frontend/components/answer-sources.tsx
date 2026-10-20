const OPENFDA_URL = "https://open.fda.gov";

// openFDA's terms (https://open.fda.gov/terms/) ask for this credit, though they don't require it.
export function OpenFdaCredit() {
  return (
    <p className="text-xs text-muted-foreground">
      Data provided by the U.S. Food and Drug Administration (
      <a
        href={OPENFDA_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline underline-offset-4"
      >
        openFDA
      </a>
      )
    </p>
  );
}
