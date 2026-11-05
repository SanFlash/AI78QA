import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "AI78QA | Autonomous QA Intelligence", description: "Train, discover, automate and improve software quality with measurable AI." };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
