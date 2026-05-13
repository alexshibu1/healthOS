/**
 * Public URLs for in-app links (GitHub repo + GitHub Pages project site).
 * Override with Vite env if your fork or Pages URL differs.
 */
const slug =
  (typeof import.meta.env.VITE_GITHUB_REPO_SLUG === "string" &&
    import.meta.env.VITE_GITHUB_REPO_SLUG.trim()) ||
  "alexshibu1/healthOS";

const [owner, repo] = slug.split("/");

export const GITHUB_REPO_SLUG = slug;

export const GITHUB_REPO_URL = `https://github.com/${slug}`;

/** Default: GitHub Pages project-site pattern for branch `main` + `/docs`. */
export const PAGES_SITE_URL =
  (typeof import.meta.env.VITE_PAGES_SITE_URL === "string" &&
    import.meta.env.VITE_PAGES_SITE_URL.trim()) ||
  (owner && repo ? `https://${owner}.github.io/${repo}/` : "https://github.com/");
