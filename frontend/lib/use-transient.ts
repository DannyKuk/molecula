import { useEffect, useState } from "react";

/** A value that clears itself `ms` after it is shown; null while nothing is shown. */
export function useTransient<T>(ms: number): [T | null, (value: T | null) => void] {
  const [value, setValue] = useState<T | null>(null);

  useEffect(() => {
    if (value === null) return;
    const timer = setTimeout(() => setValue(null), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);

  return [value, setValue];
}
