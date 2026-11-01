import type { Metadata } from "next";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";
import "@/components/report.css";

export const metadata: Metadata = {
  title: { default: "Research library · GraphIV", template: "%s · GraphIV" },
  description: "Explore GraphIV research reports and the papers and citations behind them.",
  icons: { icon: "/icon.svg" },
};

const themeScript = `try{var t=localStorage.getItem('graphiv.theme');document.documentElement.dataset.theme=t==='dark'||(!t&&matchMedia('(prefers-color-scheme:dark)').matches)?'dark':'light'}catch{}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: themeScript }} /><link rel="preload" href="/fonts/GoogleSansFlex.woff" as="font" type="font/woff" crossOrigin="anonymous" /><link rel="preload" href="/fonts/Newsreader.ttf" as="font" type="font/ttf" crossOrigin="anonymous" /></head><body><a href="#main-content" className="skip-link">Skip to content</a><SiteHeader />{children}</body></html>;
}
