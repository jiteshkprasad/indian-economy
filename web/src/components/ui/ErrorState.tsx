"use client";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import s from "./ui.module.css";

/**
 * Shown when a data file fails to load or does not match the contract (PLAN §4.4).
 * Names the file, logs to the console, and shows no numbers at all.
 */
export function ErrorState({ file, error, headingLevel = 2 }: { file: string; error?: Error | null; headingLevel?: 2 | 3 }) {
  const t = useTranslations("common.error");
  useEffect(() => {
    console.error(`[ErrorState] ${file}: ${error?.message ?? "failed to load"}`);
  }, [file, error]);
  const H = headingLevel === 2 ? "h2" : "h3";
  return (
    <div className={s.error} role="alert" data-error-file={file}>
      <H>{t("title")}</H>
      <p>{t("file", { file })}</p>
      {error?.message && <p>{error.message}</p>}
      <p>{t("noNumbers")}</p>
    </div>
  );
}
