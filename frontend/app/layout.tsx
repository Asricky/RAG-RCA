import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "5G RCA Copilot", description: "AI-assisted 5G observability and root cause analysis" };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
