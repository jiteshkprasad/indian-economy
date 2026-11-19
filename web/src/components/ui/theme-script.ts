/**
 * The theme storage key and the inline <head> script that applies a stored theme
 * before paint (PLAN §4.11).
 *
 * This module must NOT be "use client". A server component that imports a value
 * from a "use client" module receives a client reference, not the value: the
 * layouts' <script dangerouslySetInnerHTML={{ __html: THEME_HEAD_SCRIPT }}> then
 * went into the RSC payload as a reference to ThemeToggle's chunk. When that chunk
 * arrived after React had started hydrating <head>, hydration suspended inside the
 * head and resumed with the cursor in the wrong place, so React threw #418 and
 * client-rendered the whole document (verify V4-02). As a plain module the string
 * is inlined in the payload and hydration never waits on a chunk for it.
 */
export const THEME_STORAGE_KEY = "theme";

/** Runs in <head> before paint; must stay tiny and dependency-free. */
export const THEME_HEAD_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}})();`;
